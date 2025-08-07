# Rhombus Camera Footage Backup System

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Rhombus API](https://img.shields.io/badge/Rhombus-API%20v2-green.svg)](https://apidocs.rhombussystems.com/)

> **Automatically download camera footage to local NAS storage using two modes: scheduled time-based backups or incident-driven alert-based downloads.**

## 🎯 Overview

This Python script provides comprehensive backup capabilities for Rhombus camera systems, supporting both proactive scheduled backups and reactive incident response through policy alert integration.

### Key Features

- **🚨 Alert-Based Downloads**: Automatically capture footage when policy alerts are triggered
- **📅 Manual Time-Based Downloads**: Schedule regular backups for specific time periods
- **🧵 Multi-threaded Processing**: Concurrent downloads for improved performance
- **🎵 Audio Integration**: Combines video and audio streams when available
- **📁 Smart File Naming**: Organized output with metadata-rich filenames
- **🌐 Network Flexibility**: Supports both LAN and WAN connections

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or download the repository
git clone <repository-url>
cd backup-alerts-local

# Install Python dependencies
pip install -r requirements.txt

# Install FFmpeg (system dependency)
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
# Windows: Download from https://ffmpeg.org/
```

### 2. Get API Credentials

1. Log into your Rhombus Console
2. Navigate to **Settings** → **API Management**
3. Create a new API key
4. Copy the API key for use in commands

### 3. Basic Usage

**Download footage from recent alerts:**

```bash
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts
```

**Download last hour of footage:**

```bash
python3 copy_footage_script_threading.py -a YOUR_API_KEY
```

## 📋 Command Reference

### Required Arguments

- `-a, --api_key`: Your Rhombus API key

### Alert Mode Arguments

- `--alerts, -al`: Enable alert-based download mode
- `--max_alerts, -ma`: Maximum alerts to retrieve (default: 100)
- `--alert_buffer, -ab`: Buffer seconds before/after alert (default: 30)
- `--before_time, -bt`: Only get alerts before timestamp (epoch seconds)
- `--after_time, -at`: Only get alerts after timestamp (epoch seconds)

### Manual Mode Arguments

- `--start_time, -s`: Start time in epoch seconds (default: 1 hour ago)
- `--duration, -u`: Duration in seconds (default: 3600)

### Common Arguments

- `--location_uuid, -loc`: Filter by location UUID
- `--camera_uuid, -cam`: Filter by camera UUID
- `--usewan, -w`: Use WAN connection for remote access
- `--debug, -g`: Enable detailed debug logging

## 💡 Usage Examples

### Alert Mode Examples

```bash
# Download all recent alerts
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts

# Download alerts from last 24 hours with 1-minute buffer
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts \
  --after_time $(date -d '24 hours ago' +%s) --alert_buffer 60

# Download alerts from specific camera
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts \
  --camera_uuid CAMERA_UUID --debug
```

### Manual Mode Examples

```bash
# Download last hour from all cameras
python3 copy_footage_script_threading.py -a YOUR_API_KEY

# Download 2-hour period from specific camera
python3 copy_footage_script_threading.py -a YOUR_API_KEY \
  -s 1672531200 -u 7200 -cam CAMERA_UUID

# Download from location via WAN
python3 copy_footage_script_threading.py -a YOUR_API_KEY \
  -loc LOCATION_UUID -w
```

## 📁 File Structure

```
backup-alerts-local/
├── copy_footage_script_threading.py  # Main script
├── rhombus_logging.py                # Custom logging
├── rhombus_mpd_info.py              # MPD parser
├── requirements.txt                  # Dependencies
├── README.md                        # This file
├── CLAUDE.md                        # Claude Code guidance
├── Copy_Footage_Notes.md            # Detailed implementation guide
└── knowledge/
    └── general-noates.md            # API endpoint info
```

## 🔧 System Requirements

### Python Dependencies

```txt
requests>=2.25.1
urllib3>=1.26.0
ffmpeg-python>=0.2.0
```

### System Requirements

- **Python**: 3.6 or higher
- **FFmpeg**: For audio/video processing
- **Network**: Stable connection to Rhombus API
- **Storage**: ~50MB per minute of HD footage

## 📊 Output Files

### Manual Mode

```
CameraName_uuid123_1672531200_video.mp4           # Video only
CameraName_uuid123_1672531200_videoWithAudio.mp4  # Video + Audio
```

### Alert Mode

```
CameraName_uuid123_20240101_143022_alert_motion_alert456_video.mp4     # Video only
CameraName_uuid123_20240101_143022_alert_motion_alert456_combined.mp4  # Video + Audio
```

**Filename Components:**

- **CameraName**: Sanitized camera name
- **uuid123**: Camera UUID
- **20240101_143022**: Timestamp (YYYYMMDD_HHMMSS)
- **motion**: Alert type
- **alert456**: Alert ID

## 🚀 Production Deployment

### Automated Scheduling

Add to crontab (`crontab -e`):

```bash
# Hourly alert check
0 * * * * cd /path/to/script && python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts

# Daily backup at 2 AM
0 2 * * * cd /path/to/script && python3 copy_footage_script_threading.py -a YOUR_API_KEY -s $(date -d 'yesterday 00:00:00' +%s) -u 86400
```

### Monitoring

```bash
# Check recent downloads
ls -la *.mp4 | head -10

# Monitor disk usage
df -h .

# Check for errors
tail -f /var/log/rhombus-backup.log | grep -i error
```

## 🐛 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "No policy alerts found" | Check time filters and alert policies |
| "Alert missing timestamp" | Enable debug mode to see malformed alerts |
| "Failed to retrieve alerts" | Verify API key permissions |
| FFmpeg errors | Install FFmpeg and ensure PATH access |

### Debug Mode

```bash
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts --debug
```

Debug output includes:

- API response data
- Alert processing steps
- Download progress
- Detailed error messages

## 📖 Documentation

- **[Copy_Footage_Notes.md](Copy_Footage_Notes.md)**: Complete implementation guide
- **[CLAUDE.md](CLAUDE.md)**: Claude Code development guidance
- **[Rhombus API Docs](https://apidocs.rhombussystems.com/)**: Official API documentation

## 🎯 Use Cases

### 🏢 Corporate Security

Monitor business locations during operating hours with automatic incident capture.

### 🏪 Retail Loss Prevention

High-frequency monitoring for theft prevention with extended context buffers.

### 🏭 Manufacturing Compliance

Safety incident documentation with location-specific filtering.

### 🏠 Multi-site Management

Centralized footage backup across multiple locations.

## 📈 Performance

- **Threading**: 4 concurrent workers (configurable)
- **Rate Limiting**: 0.1s delay between requests
- **Storage**: ~50MB per minute (HD), ~150MB (4K)
- **Bandwidth**: Optimized for both LAN and WAN usage

## 🛡️ Security

- API key authentication
- HTTPS connections to Rhombus API
- Optional certificate-based authentication
- Secure federated session tokens

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

### Resources

- [Rhombus API Documentation](https://apidocs.rhombussystems.com/)
- [Epoch Time Converter](https://www.epochconverter.com/)
- [Cron Expression Generator](https://crontab.guru/)

### Getting Help

1. Enable debug mode with `--debug`
2. Check the detailed implementation guide
3. Review API permissions and connectivity
4. Contact Rhombus support with debug logs

---

> 💡 **Pro Tip**: Start with alert mode (`--alerts`) for automatic incident capture, then use manual mode for specific investigations. This combination provides comprehensive security coverage.

## 🔄 Recent Updates

- ✅ Added alert-based download functionality
- ✅ Implemented configurable buffer times
- ✅ Enhanced multi-threading support
- ✅ Improved error handling and logging
- ✅ Added production deployment guidance