###################################################################################
# Copyright (c) 2021 Rhombus Systems                                              #
#                                                                                 #
# Permission is hereby granted, free of charge, to any person obtaining a copy    #
# of this software and associated documentation files (the "Software"), to deal   #
# in the Software without restriction, including without limitation the rights    #
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell       #
# copies of the Software, and to permit persons to whom the Software is           #
# furnished to do so, subject to the following conditions:                        #
#                                                                                 #
# The above copyright notice and this permission notice shall be included in all  #
# copies or substantial portions of the Software.                                 #
#                                                                                 #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR      #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,        #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE     #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER          #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,   #
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE   #
# SOFTWARE.                                                                       #
###################################################################################
import argparse
import json
import sys
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict
import ffmpeg
import os

import requests
import urllib3

import rhombus_logging

# just to prevent unnecessary logging since we are not verifying the host
from rhombus_mpd_info import RhombusMPDInfo

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_logger = rhombus_logging.get_logger("rhombus.CopyFootageToLocalStorage")

URI_FILE_ENDINGS = ["clip.mpd", "file.mpd"]


def init_argument_parser():
    parser = argparse.ArgumentParser(
        description="Pulls footage from cameras based on policy alerts or manual time ranges and stores it to the filesystem."
    )
    parser.add_argument(
        "--api_key", "-a", type=str, required=True, help="Rhombus API key"
    )
    parser.add_argument(
        "--cert", "-c", type=str, required=False, help="Path to API cert"
    )
    parser.add_argument(
        "--private_key", "-p", type=str, required=False, help="Path to API private key"
    )
    parser.add_argument(
        "--start_time",
        "-s",
        type=int,
        required=False,
        help="Start time in epoch seconds (ignored when using --alerts mode)",
        default=int((datetime.now() - timedelta(hours=1)).timestamp()),
    )
    parser.add_argument(
        "--duration",
        "-u",
        type=int,
        required=False,
        help="Duration in seconds (ignored when using --alerts mode)",
        default=1 * 60 * 60,
    )
    parser.add_argument(
        "--debug", "-g", required=False, action="store_true", help="Print debug logging"
    )
    parser.add_argument(
        "--usewan",
        "-w",
        required=False,
        help="Use a WAN connection to download rather than a LAN connection",
        action="store_true",
    )
    parser.add_argument(
        "--location_uuid", "-loc", type=str, required=False, help="Location UUID"
    )
    parser.add_argument(
        "--camera_uuid", "-cam", type=str, required=False, help="Camera UUID"
    )
    parser.add_argument(
        "--alerts", "-al", required=False, action="store_true", 
        help="Download footage based on policy alerts instead of manual time range"
    )
    parser.add_argument(
        "--max_alerts", "-ma", type=int, required=False, default=100,
        help="Maximum number of alerts to retrieve (default: 100)"
    )
    parser.add_argument(
        "--before_time", "-bt", type=int, required=False,
        help="Only get alerts before this timestamp (epoch seconds)"
    )
    parser.add_argument(
        "--after_time", "-at", type=int, required=False,
        help="Only get alerts after this timestamp (epoch seconds)"
    )
    parser.add_argument(
        "--alert_buffer", "-ab", type=int, required=False, default=30,
        help="Buffer time in seconds before and after alert (default: 30)"
    )
    return parser


def get_segment_uri(mpd_uri, segment_name):
    for ending in URI_FILE_ENDINGS:
        if ending in mpd_uri:
            return mpd_uri.replace(ending, segment_name)
    return None


def get_segment_uri_index(rhombus_mpd_info, mpd_uri, index):
    segment_name = rhombus_mpd_info.segment_pattern.replace(
        "$Number$", str(index + rhombus_mpd_info.start_index)
    )
    return get_segment_uri(mpd_uri, segment_name)


def get_policy_alerts(api_key, max_results=100, location_uuid=None, camera_uuid=None, 
                     before_timestamp_ms=None, after_timestamp_ms=None):
    url = "https://api2.rhombussystems.com/api/event/getPolicyAlerts"
    
    headers = {
        "accept": "application/json",
        "x-auth-scheme": "api-token",
        "content-type": "application/json",
        "x-auth-apikey": api_key,
    }
    
    body = {
        "maxResults": max_results,
        "locationFilter": location_uuid,
        "deviceFilter": camera_uuid,
        "beforeTimestampMs": before_timestamp_ms,
        "afterTimestampMs": after_timestamp_ms
    }
    
    try:
        response = requests.post(url, headers=headers, json=body)
        _logger.debug("Policy alerts response: %s", response.content)
        
        if response.status_code != 200:
            _logger.error("Failed to retrieve policy alerts: %s", response.content)
            return []
            
        alerts_data = response.json()
        _logger.info("Retrieved %d policy alerts", len(alerts_data.get('alerts', [])))
        return alerts_data.get('alerts', [])
        
    except Exception as e:
        _logger.error("Error retrieving policy alerts: %s", e)
        return []


def process_alerts_for_download(alerts, alert_buffer_seconds=30):
    download_tasks = []
    
    for alert in alerts:
        try:
            # Extract timing information (assuming millisecond timestamps)
            alert_timestamp_ms = alert.get('timestampMs') or alert.get('eventStartMs')
            event_end_ms = alert.get('eventEndMs')
            
            if not alert_timestamp_ms:
                _logger.warning("Alert missing timestamp information, skipping: %s", alert.get('alertId', 'unknown'))
                continue
                
            # Convert to seconds and add buffer
            start_time = (alert_timestamp_ms // 1000) - alert_buffer_seconds
            
            if event_end_ms:
                duration = ((event_end_ms - alert_timestamp_ms) // 1000) + (2 * alert_buffer_seconds)
            else:
                # Default to 2 minutes if no end time
                duration = 120 + (2 * alert_buffer_seconds)
                
            # Extract device information
            device_uuid = alert.get('deviceUuid') or alert.get('cameraUuid')
            device_name = alert.get('deviceName') or alert.get('cameraName', 'Unknown')
            alert_id = alert.get('alertId', 'unknown')
            alert_type = alert.get('alertType', 'alert')
            
            if not device_uuid:
                _logger.warning("Alert missing device UUID, skipping: %s", alert_id)
                continue
                
            download_task = {
                'device_uuid': device_uuid,
                'device_name': device_name,
                'start_time': max(0, start_time),  # Ensure non-negative
                'duration': duration,
                'alert_id': alert_id,
                'alert_type': alert_type,
                'timestamp_ms': alert_timestamp_ms
            }
            
            download_tasks.append(download_task)
            _logger.info("Prepared download task for alert %s on device %s (%s)", 
                        alert_id, device_name, device_uuid)
                        
        except Exception as e:
            _logger.error("Error processing alert: %s", e)
            continue
    
    _logger.info("Prepared %d download tasks from %d alerts", len(download_tasks), len(alerts))
    return download_tasks


# This method gets the uuids of cameras and pairs them with any associated audio device

def get_camera_to_gateway_map(api_key, location_uuid=None, camera_uuid=None):
    url_cam = "https://api2.rhombussystems.com/api/camera/getMinimalCameraStateList"
    url_aud = "https://api2.rhombussystems.com/api/audiogateway/getMinimalAudioGatewayStateList"

    # camUuid : {name : camera name, audioGatewayUuid : uuid}
    camUuidDict = {}

    headers = {
        "accept": "application/json",
        "x-auth-scheme": "api-token",
        "content-type": "application/json",
        "x-auth-apikey": api_key,
    }
    body = {}

    response = requests.post(url_cam, headers=headers, json=body)
    camResDict = json.loads(response.text)

    response = requests.post(url_aud, headers=headers, json=body)
    audResDict = json.loads(response.text)

    # if there is a args_main.location_uuid in the argument then filter out and only add cameraUuids to the uuid_lst that have the same locationUuid

    for cam in camResDict["cameraStates"]:
        if cam["connectionStatus"] == "RED":
            continue
        camNameDict = {"name": cam["name"]}

        if location_uuid is not None and cam["locationUuid"] != location_uuid:
            continue
        if camera_uuid is not None and cam["uuid"] != camera_uuid:
            continue

        camUuidDict[cam["uuid"]] = camNameDict

        for audioGateway in audResDict["audioGatewayStates"]:
            for cameraUuid in audioGateway["associatedCameras"]:
                if cameraUuid in camUuidDict:
                    camUuidDict[cameraUuid]["audioGatewayUuid"] = audioGateway["uuid"]

    print("  ---------------------- camUuidDict")
    print(camUuidDict)

    return camUuidDict


class CopyFootageToLocalStorage:
    def __init__(self, args: Dict[any, any], cam: str, video_file_name: str, audio_file_name: str):
        # If debug flag is set, enable logging at DEBUG level
        if args.debug:
            _logger.setLevel("DEBUG")

        # Initialize object variables
        self.api_url = "https://api2.rhombussystems.com"
        self.device_id = cam
        self.video = video_file_name
        self.audio = audio_file_name
        self.use_wan = args.usewan

        # Set start_time and duration from arguments, default is handled in argument definition
        self.start_time = args.start_time
        self.duration = args.duration

        # Initialize API and media sessions
        self.api_sess = requests.session()
        self.api_sess.verify = False
        self.media_sess = requests.session()
        self.media_sess.verify = False

        # Set authentication headers based on arguments
        if args.cert and args.private_key:
            scheme = "api"
            self.api_sess.cert = (args.cert, args.private_key)
        else:
            scheme = "api-token"
        self.api_sess.headers = {"x-auth-scheme": scheme, "x-auth-apikey": args.api_key}
        self.media_sess.headers = {
            "x-auth-scheme": scheme,
            "x-auth-apikey": args.api_key,
        }

    def execute_video(self):
        # get a federated session token for media that lasts 1 hour
        session_req_payload = {"durationSec": 60 * 60}
        session_req_resp = self.api_sess.post(
            self.api_url + "/api/org/generateFederatedSessionToken",
            json=session_req_payload,
        )
        _logger.debug("Federated session token response: %s", session_req_resp.content)

        if session_req_resp.status_code != 200:
            _logger.warn(
                "Failed to retrieve federated session token, cannot continue: %s",
                session_req_resp.content,
            )
            return

        federated_session_token = session_req_resp.json()["federatedSessionToken"]
        session_req_resp.close()

        _logger.debug("  ---------------------- before getMediaUris ")
        # get camera media uris
        media_uri_payload = {"cameraUuid": self.device_id}
        media_uri_resp = self.api_sess.post(
            self.api_url + "/api/camera/getMediaUris", json=media_uri_payload
        )
        _logger.debug("Camera media uri response: %s", media_uri_resp.content)

        if session_req_resp.status_code != 200:
            _logger.warn(
                "Failed to retrieve camera media uris, cannot continue: %s",
                media_uri_resp.content,
            )
            return

        mpd_uri_template = (
            media_uri_resp.json()["wanVodMpdUriTemplate"]
            if self.use_wan
            else media_uri_resp.json()["lanVodMpdUrisTemplates"][0]
        )

        _logger.debug("Raw mpd uri template: %s", mpd_uri_template)
        media_uri_resp.close()

        """ 
        When we make requests to the camera, the camera will use our session information to serve the correct files.
        The MPD document call starts the session and tells the camera the start time and duration of the clip requested
        We then get the seg_init.mp4 file which has the appropriate mp4 headers/init data
        and then we get the actual video segment files, named seg_1.m4v, seg_2.m4v, where each segment is a 2 second
        segment of video, so we need to go up to seg_<duration/2>.m4v.  The camera will automatically send the correct
        absolute time segments for each of the clip segments.  Concatenating the seg_init.mp4 and seg_#.m4v files into 
        a single .mp4 gives the playable video.
        """

        # the template has placeholders for where the clip start time and duration are supposed to go, so put the
        # desired start time and duration in the template
        mpd_uri = mpd_uri_template.replace(
            "{START_TIME}", str(self.start_time)
        ).replace("{DURATION}", str(self.duration))
        _logger.debug(" ---------------------- Mpd uri: %s", mpd_uri)

        # use the federated session token as our session id for the camera to process our requests
        media_headers = {"Cookie": "RSESSIONID=RFT:" + str(federated_session_token)}

        # start media session with camera by requesting the MPD file
        mpd_doc_resp = self.media_sess.get(mpd_uri, headers=media_headers)
        _logger.debug("Mpd doc: %s", mpd_doc_resp.content)
        mpd_info = RhombusMPDInfo(str(mpd_doc_resp.content, "utf-8"), False)
        mpd_doc_resp.close()

        # start writing the video stream
        with open(self.video, "wb") as output_fp:
            # first write the init file
            init_seg_uri = get_segment_uri(mpd_uri, mpd_info.init_string)
            _logger.debug("Init segment uri: %s", init_seg_uri)

            init_seg_resp = self.media_sess.get(init_seg_uri, headers=media_headers)
            _logger.debug("seg_init_resp: %s", init_seg_resp)

            output_fp.write(init_seg_resp.content)
            output_fp.flush()
            init_seg_resp.close()

            # now write the actual video segment files.
            # Each segment is 2 seconds, so we have a total of duration / 2 segments to download
            for cur_seg in range(int(self.duration / 2)):
                seg_uri = get_segment_uri_index(mpd_info, mpd_uri, cur_seg)
                _logger.debug("Segment uri: %s", seg_uri)

                seg_resp = self.media_sess.get(seg_uri, headers=media_headers)
                _logger.debug("seg_resp: %s", seg_resp)

                output_fp.write(seg_resp.content)
                output_fp.flush()
                seg_resp.close()

                # log every 10 minutes of footage downloaded
                if cur_seg > 0 and cur_seg % 300 == 0:
                    _logger.info(
                        "Segments written from [%s] - [%s]",
                        datetime.fromtimestamp(
                            self.start_time + ((cur_seg - 300) * 2)
                        ).strftime("%c"),
                        datetime.fromtimestamp(
                            self.start_time + (cur_seg * 2)
                        ).strftime("%c"),
                    )

        _logger.info(
            "Succesfully downloaded video from [%s] - [%s] to %s",
            datetime.fromtimestamp(self.start_time).strftime("%c"),
            datetime.fromtimestamp(self.start_time + self.duration).strftime("%c"),
            self.video,
        )

    def execute_audio(self, audioGatewayUuid):
        # get a federated session token for media that lasts 1 hour
        session_req_payload = {"durationSec": 60 * 60}
        session_req_resp = self.api_sess.post(self.api_url + "/api/org/generateFederatedSessionToken",
                                              json=session_req_payload)
        _logger.debug("Federated session token response: %s", session_req_resp.content)

        if session_req_resp.status_code != 200:
            _logger.warn("Failed to retrieve federated session token, cannot continue: %s", session_req_resp.content)
            return

        federated_session_token = session_req_resp.json()["federatedSessionToken"]
        session_req_resp.close()

        # get camera media uris
        media_uri_payload = {"gatewayUuid": audioGatewayUuid}
        media_uri_resp = self.api_sess.post(self.api_url + "/api/audiogateway/getMediaUris",
                                            json=media_uri_payload)

        _logger.debug("Audio media uri response: %s", media_uri_resp.content)
        if session_req_resp.status_code != 200:
            _logger.warn("Failed to retrieve audio media uris, cannot continue: %s", media_uri_resp.content)
            return

        if self.use_wan:
            mpd_uri_template = media_uri_resp.json()["wanVodMpdUriTemplate"]
        else:
            mpd_uri_template = media_uri_resp.json()["lanVodMpdUrisTemplates"][0]

        _logger.debug("Raw mpd uri template: %s", mpd_uri_template)
        media_uri_resp.close()

        # the template has placeholders for where the clip start time and duration are supposed to go, so put the
        # desired start time and duration in the template

        # Lets subtract 1 second to equate for 1 second audiostream delay
        mpd_uri = mpd_uri_template.replace("{START_TIME}", str(self.start_time)).replace("{DURATION}",
                                                                                         str(self.duration))
        _logger.debug("Mpd uri: %s", mpd_uri)

        # use the federated session token as our session id for the audio to process our requests
        media_headers = {"Cookie": "RSESSIONID=RFT:" + str(federated_session_token)}

        # start media session with audio by requesting the MPD file
        mpd_doc_resp = self.media_sess.get(mpd_uri, headers=media_headers)
        _logger.debug("Mpd doc: %s", mpd_doc_resp.content)

        print(" ---------------------- before audio mpd_info")
        mpd_info = RhombusMPDInfo(str(mpd_doc_resp.content, 'utf-8'), True)
        print(" ---------------------- after audio mpd_info")
        mpd_doc_resp.close()

        # start writing the audio stream
        # with open(self.audio, "wb") as output_fp: prev line, need to programatically handle audio file name
        print(" ---------------------- before creation of audio_out file")
        with open(self.audio, "wb") as output_fp:
            print(" ---------------------- top of audio_out creation")
            # first write the init file
            init_seg_uri = get_segment_uri(mpd_uri, mpd_info.init_string)
            _logger.debug("Init segment uri: %s", init_seg_uri)

            init_seg_resp = self.media_sess.get(init_seg_uri, headers=media_headers)
            _logger.debug("seg_init_resp: %s", init_seg_resp)

            output_fp.write(init_seg_resp.content)
            output_fp.flush()
            init_seg_resp.close()

            # now write the actual audio segment files.
            # Each segment is 2 seconds, so we have a total of duration / 2 segments to download
            for cur_seg in range(int(self.duration / 2)):
                seg_uri = get_segment_uri_index(mpd_info, mpd_uri,
                                                cur_seg)
                _logger.debug("Segment uri: %s", seg_uri)

                seg_resp = self.media_sess.get(seg_uri, headers=media_headers)
                _logger.debug("seg_resp: %s", seg_resp)

                output_fp.write(seg_resp.content)
                output_fp.flush()
                seg_resp.close()

                # log every 10 minutes of footage downloaded
                if cur_seg > 0 and cur_seg % 300 == 0:
                    _logger.debug("Segments written from [%s] - [%s]",
                                  datetime.fromtimestamp(self.start_time + ((cur_seg - 300) * 2)).strftime('%c'),
                                  datetime.fromtimestamp(self.start_time + (cur_seg * 2)).strftime('%c'))

        _logger.debug("Succesfully downloaded audio from [%s] - [%s] to %s",
                      datetime.fromtimestamp(self.start_time).strftime('%c'),
                      datetime.fromtimestamp(self.start_time + self.duration).strftime('%c'),
                      self.audio)


def worker_manual(camKey, camVal, audioGatewayUuid, args_main):
    time.sleep(0.1)  # introduce a small delay to avoid hitting rate limits
    cam_uuid = camKey
    cam_name = camVal["name"]
    _logger.debug(" ---------------------- saving footage for %s" % cam_name)

    file_type = ".webm" if audioGatewayUuid is not None else ".mp4"

    video_file = (
            "".join(x for x in cam_name if x.isalnum())
            + "_"
            + cam_uuid
            + "_"
            + str(args_main.start_time)
            + "_video"
            + file_type
    )
    print(" ---------------------- audioGatewayUuid %s" % audioGatewayUuid)
    if audioGatewayUuid is not None:
        print(" ---------------------- top of audioGatewayUuid is not None")
        audio_file = (
                "".join(x for x in cam_name if x.isalnum())
                + "_"
                + cam_uuid
                + "_"
                + str(args_main.start_time)
                + "_audio"
                + file_type
        )
        engine = CopyFootageToLocalStorage(args_main, cam_uuid, video_file, audio_file)
        engine.execute_video()
        engine.execute_audio(audioGatewayUuid)
        try:
            input_video = ffmpeg.input(video_file)
            input_audio = ffmpeg.input(audio_file)
            output_file = "".join(x for x in cam_name if x.isalnum()) + "_" + cam_uuid + "_" + str(
                args_main.start_time) + "_videoWithAudio.mp4"
            ffmpeg.concat(input_video, input_audio, v=1, a=1).output(output_file).run(overwrite_output=True)
            os.remove(audio_file)
            os.remove(video_file)
            print(f"Successfully created {output_file} and removed original files.")
        except ffmpeg.Error as e:
            print(f"Error in ffmpeg processing: {e}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        engine = CopyFootageToLocalStorage(args_main, cam_uuid, video_file, None)
        engine.execute_video()


def worker_alert(download_task, audioGatewayUuid, args_main):
    time.sleep(0.1)  # introduce a small delay to avoid hitting rate limits
    
    cam_uuid = download_task['device_uuid']
    cam_name = download_task['device_name']
    alert_id = download_task['alert_id']
    alert_type = download_task['alert_type']
    start_time = download_task['start_time']
    duration = download_task['duration']
    
    _logger.info("Processing alert %s (%s) for camera %s", alert_id, alert_type, cam_name)

    file_type = ".webm" if audioGatewayUuid is not None else ".mp4"

    # Create filename with alert information
    safe_cam_name = "".join(x for x in cam_name if x.isalnum())
    safe_alert_id = "".join(x for x in alert_id if x.isalnum())
    safe_alert_type = "".join(x for x in alert_type if x.isalnum())
    
    timestamp_str = datetime.fromtimestamp(start_time).strftime("%Y%m%d_%H%M%S")
    
    video_file = (
        f"{safe_cam_name}_{cam_uuid}_{timestamp_str}_alert_{safe_alert_type}_{safe_alert_id}_video{file_type}"
    )
    
    if audioGatewayUuid is not None:
        audio_file = (
            f"{safe_cam_name}_{cam_uuid}_{timestamp_str}_alert_{safe_alert_type}_{safe_alert_id}_audio{file_type}"
        )
        
        # Create a modified args object with alert timing
        class AlertArgs:
            def __init__(self, base_args, start_time, duration):
                # Copy all attributes from base_args
                for attr in dir(base_args):
                    if not attr.startswith('_'):
                        setattr(self, attr, getattr(base_args, attr))
                # Override timing
                self.start_time = start_time
                self.duration = duration
        
        alert_args = AlertArgs(args_main, start_time, duration)
        
        engine = CopyFootageToLocalStorage(alert_args, cam_uuid, video_file, audio_file)
        engine.execute_video()
        engine.execute_audio(audioGatewayUuid)
        
        try:
            input_video = ffmpeg.input(video_file)
            input_audio = ffmpeg.input(audio_file)
            output_file = f"{safe_cam_name}_{cam_uuid}_{timestamp_str}_alert_{safe_alert_type}_{safe_alert_id}_combined.mp4"
            ffmpeg.concat(input_video, input_audio, v=1, a=1).output(output_file).run(overwrite_output=True)
            os.remove(audio_file)
            os.remove(video_file)
            _logger.info("Successfully created %s for alert %s", output_file, alert_id)
        except ffmpeg.Error as e:
            _logger.error("Error in ffmpeg processing for alert %s: %s", alert_id, e)
        except Exception as e:
            _logger.error("Error processing alert %s: %s", alert_id, e)
    else:
        # Create a modified args object with alert timing
        class AlertArgs:
            def __init__(self, base_args, start_time, duration):
                # Copy all attributes from base_args
                for attr in dir(base_args):
                    if not attr.startswith('_'):
                        setattr(self, attr, getattr(base_args, attr))
                # Override timing
                self.start_time = start_time
                self.duration = duration
        
        alert_args = AlertArgs(args_main, start_time, duration)
        engine = CopyFootageToLocalStorage(alert_args, cam_uuid, video_file, None)
        engine.execute_video()
        _logger.info("Successfully created %s for alert %s", video_file, alert_id)


if __name__ == "__main__":
    # this cli command will save the last hour of footage from the specified device
    # python3 copy_footage_to_local_storage.py -a "<API TOKEN>" -d "<DEVICE ID>" -o out.mp4
    t0 = time.time()
    print(" ---------------------- start time %s" % t0)
    arg_parser = init_argument_parser()
    args_main = arg_parser.parse_args(sys.argv[1:])

    if args_main.alerts:
        # Alert-based mode: get policy alerts and download corresponding footage
        _logger.info("Running in alerts mode - fetching policy alerts...")
        
        # Convert time arguments to milliseconds if provided
        before_timestamp_ms = None
        after_timestamp_ms = None
        if args_main.before_time:
            before_timestamp_ms = args_main.before_time * 1000
        if args_main.after_time:
            after_timestamp_ms = args_main.after_time * 1000
            
        # Get policy alerts
        alerts = get_policy_alerts(
            api_key=args_main.api_key,
            max_results=args_main.max_alerts,
            location_uuid=args_main.location_uuid,
            camera_uuid=args_main.camera_uuid,
            before_timestamp_ms=before_timestamp_ms,
            after_timestamp_ms=after_timestamp_ms
        )
        
        if not alerts:
            _logger.warning("No policy alerts found matching criteria")
            sys.exit(0)
            
        # Process alerts into download tasks
        download_tasks = process_alerts_for_download(alerts, args_main.alert_buffer)
        
        if not download_tasks:
            _logger.warning("No valid download tasks generated from alerts")
            sys.exit(0)
            
        # Get camera to audio gateway mapping for the relevant devices
        relevant_device_uuids = set(task['device_uuid'] for task in download_tasks)
        camUuidDict = get_camera_to_gateway_map(
            args_main.api_key, args_main.location_uuid, args_main.camera_uuid
        )
        
        # Execute download tasks
        _logger.info("Starting download of %d alert clips...", len(download_tasks))
        with ThreadPoolExecutor(max_workers=4) as executor:
            for download_task in download_tasks:
                device_uuid = download_task['device_uuid']
                # Find audio gateway for this device if available
                audioGatewayUuid = None
                for cam_uuid, cam_data in camUuidDict.items():
                    if cam_uuid == device_uuid:
                        audioGatewayUuid = cam_data.get("audioGatewayUuid", None)
                        break
                
                executor.submit(worker_alert, download_task, audioGatewayUuid, args_main)
                
    else:
        # Manual mode: use original functionality
        _logger.info("Running in manual mode - downloading footage for specified time range...")
        camUuidDict = get_camera_to_gateway_map(
            args_main.api_key, args_main.location_uuid, args_main.camera_uuid
        )
        with ThreadPoolExecutor(max_workers=4) as executor:  # limit to 4 concurrent threads
            for camKey, camVal in camUuidDict.items():
                audioGatewayUuid = camVal.get("audioGatewayUuid", None)
                executor.submit(worker_manual, camKey, camVal, audioGatewayUuid, args_main)

    t1 = time.time()
    elapsed_time = t1 - t0
    print(" ---------------------- end time %s" % t1)
    print(
        f" ---------------------- Total execution time: {elapsed_time / 60:.2f} minutes"
    )
