# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based backup and alerting system for Rhombus camera footage. It downloads video and audio recordings from Rhombus cameras to local storage using multithreading for concurrent downloads.

## Key Components

- `copy_footage_script_threading.py` - Main script that handles camera footage backup with threading support
- `rhombus_logging.py` - Custom logging formatter and configuration for Rhombus applications  
- `rhombus_mpd_info.py` - MPD (Media Presentation Description) document parser for video/audio streams
- `requirements.txt` - Python dependencies: requests, urllib3, ffmpeg-python

## Dependencies

Install dependencies with:
```bash
pip install -r requirements.txt
```

Required system dependencies:
- FFmpeg (for audio/video processing)

## Running the Application

The main script supports two modes: **Manual Mode** (time-based) and **Alert Mode** (policy alert-based).

### Manual Mode (Default)
Downloads footage based on specified time range:

```bash
python copy_footage_script_threading.py -a <API_KEY> [options]
```

### Alert Mode  
Downloads footage based on policy alerts:

```bash
python copy_footage_script_threading.py -a <API_KEY> --alerts [options]
```

### Required Arguments
- `-a, --api_key` - Rhombus API key (required)

### Manual Mode Arguments
- `-s, --start_time` - Start time in epoch seconds (default: 1 hour ago)
- `-u, --duration` - Duration in seconds (default: 3600 seconds/1 hour)

### Alert Mode Arguments
- `-al, --alerts` - Enable alert-based download mode
- `-ma, --max_alerts` - Maximum number of alerts to retrieve (default: 100)
- `-bt, --before_time` - Only get alerts before this timestamp (epoch seconds)
- `-at, --after_time` - Only get alerts after this timestamp (epoch seconds)
- `-ab, --alert_buffer` - Buffer time in seconds before and after alert (default: 30)

### Common Arguments
- `-loc, --location_uuid` - Location UUID to filter cameras/alerts by location
- `-cam, --camera_uuid` - Specific camera UUID to filter by camera
- `-w, --usewan` - Use WAN connection instead of LAN
- `-g, --debug` - Enable debug logging
- `-c, --cert` - Path to API certificate (optional)
- `-p, --private_key` - Path to API private key (optional)

### Examples

Manual mode - download last hour from all cameras:
```bash
python copy_footage_script_threading.py -a YOUR_API_KEY
```

Alert mode - download all recent alerts:
```bash
python copy_footage_script_threading.py -a YOUR_API_KEY --alerts
```

Alert mode - download alerts from specific camera with 1-minute buffer:
```bash
python copy_footage_script_threading.py -a YOUR_API_KEY --alerts --camera_uuid CAM_UUID --alert_buffer 60
```

## Architecture

### Manual Mode Process
1. Generates federated session token for authentication
2. Retrieves camera media URIs (LAN or WAN based)
3. Downloads MPD document to understand stream structure
4. Downloads video segments (2-second chunks) sequentially
5. Concatenates segments into final MP4 file

### Alert Mode Process
1. Calls `getPolicyAlerts` API to retrieve policy-triggered alerts
2. Processes each alert to extract timing and device information
3. Calculates start/end times with configurable buffer periods
4. Downloads footage for each alert using same video download process
5. Creates alert-specific filenames with alert metadata

### Audio Processing
- Detects cameras with associated audio gateways
- Downloads audio segments in parallel with video
- Uses FFmpeg to combine video and audio into single MP4 file
- Cleans up intermediate files after successful combination

### Threading
- Uses ThreadPoolExecutor with max 4 concurrent workers
- Each camera/alert is processed in separate thread to improve performance
- Includes rate limiting (0.1s delay between thread starts)

## API Integration

Connects to Rhombus API endpoints:
- `https://api2.rhombussystems.com/api/event/getPolicyAlerts` - Retrieves policy alerts
- `https://api2.rhombussystems.com/api/camera/getMinimalCameraStateList` - Gets camera states
- `https://api2.rhombussystems.com/api/audiogateway/getMinimalAudioGatewayStateList` - Gets audio gateways
- `https://api2.rhombussystems.com/api/camera/getMediaUris` - Gets media download URLs
- `https://api2.rhombussystems.com/api/org/generateFederatedSessionToken` - Auth for media downloads

## File Output

### Manual Mode Files
- Video only: `{camera_name}_{camera_uuid}_{start_time}_video.mp4`
- With audio: `{camera_name}_{camera_uuid}_{start_time}_videoWithAudio.mp4`

### Alert Mode Files  
- Video only: `{camera_name}_{camera_uuid}_{timestamp}_alert_{alert_type}_{alert_id}_video.mp4`
- With audio: `{camera_name}_{camera_uuid}_{timestamp}_alert_{alert_type}_{alert_id}_combined.mp4`

Alert files include metadata in filenames:
- `timestamp` - When the alert-based footage starts (YYYYMMDD_HHMMSS format)
- `alert_type` - Type of alert that triggered the download
- `alert_id` - Unique identifier for the specific alert

## Ongoing Development Tasks

- Review `@knowledge/general-noates.md` to update local to NAS script with specific time segments
- Goal: Use `getPolicyAlerts` to retrieve timestamps and pull corresponding video clips to local NAS
- Requires detailed review of current implementation and requirements for targeted video clip extraction