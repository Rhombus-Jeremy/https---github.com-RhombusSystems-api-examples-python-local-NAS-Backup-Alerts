# Rhombus Camera Footage Copy Script - Complete Implementation Guide

> **🎯 Purpose**: Automatically download camera footage to local NAS storage using two modes: scheduled time-based backups or incident-driven alert-based downloads.

## 📋 Overview

This script supports **TWO MODES** for downloading camera footage from Rhombus cameras:

### 🕒 **MODE 1: MANUAL MODE** (Original Functionality)
Downloads footage based on specified time ranges - ideal for:
- Scheduled daily/weekly backups
- Specific incident investigation
- Regular archival processes

### 🚨 **MODE 2: ALERT MODE** (New Functionality) 
Downloads footage based on policy alerts - perfect for:
- Automatic incident capture
- Security event documentation
- Compliance requirements

---

## 🚀 Quick Start

### Prerequisites
```bash
# Install Python dependencies
pip install -r requirements.txt

# Ensure FFmpeg is installed
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
# Windows: Download from https://ffmpeg.org/
```

### Basic Usage

**📥 Download Recent Alerts (Recommended)**
```bash
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts
```

**📅 Download Last Hour (Manual)**
```bash
python3 copy_footage_script_threading.py -a YOUR_API_KEY
```

---

## ⚙️ Command Line Arguments

### 🔑 Required Arguments
| Argument | Short | Description |
|----------|-------|-------------|
| `--api_key` | `-a` | **Rhombus API key** (Get from Console → API Management) |

### 🕒 Manual Mode Arguments
| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--start_time` | `-s` | 1 hour ago | Start time in epoch seconds ([converter](https://www.epochconverter.com/)) |
| `--duration` | `-u` | 3600 | Duration in seconds (3600 = 1 hour) |

### 🚨 Alert Mode Arguments
| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--alerts` | `-al` | - | **Enable alert-based download mode** |
| `--max_alerts` | `-ma` | 100 | Maximum number of alerts to retrieve |
| `--before_time` | `-bt` | - | Only get alerts before this timestamp (epoch seconds) |
| `--after_time` | `-at` | - | Only get alerts after this timestamp (epoch seconds) |
| `--alert_buffer` | `-ab` | 30 | Buffer time in seconds before/after each alert |

### 🔧 Common Arguments (Both Modes)
| Argument | Short | Description |
|----------|-------|-------------|
| `--cert` | `-c` | Path to API certificate (optional) |
| `--private_key` | `-p` | Path to API private key (optional) |
| `--debug` | `-g` | Enable detailed debug logging |
| `--usewan` | `-w` | Use WAN connection (for remote access) |
| `--location_uuid` | `-loc` | Filter by specific location ([API ref](https://apidocs.rhombussystems.com/reference/getlocations)) |
| `--camera_uuid` | `-cam` | Filter by specific camera ([API ref](https://apidocs.rhombussystems.com/reference/getcameraconfig)) |

---

## 💡 Usage Examples

### 📅 Manual Mode Examples

**Basic: Download last hour from all cameras**
```bash
python3 copy_footage_script_threading.py -a YOUR_API_KEY
```

**Advanced: Specific time period from specific camera**
```bash
python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  -s 1672531200 \
  -u 7200 \
  -cam CAMERA_UUID
```

**Location-based: All cameras at specific location via WAN**
```bash
python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  -loc LOCATION_UUID \
  -w
```

### 🚨 Alert Mode Examples

**Basic: Download all recent alerts**
```bash
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts
```

**Time-filtered: Alerts from last 24 hours with 1-minute buffer**
```bash
python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  --alerts \
  --after_time $(date -d '24 hours ago' +%s) \
  --alert_buffer 60
```

**Camera-specific: Alerts from specific camera with debug logging**
```bash
python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  --alerts \
  --camera_uuid CAM_UUID \
  --debug
```

**Limited: Last 50 alerts from specific location**
```bash
python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  --alerts \
  --location_uuid LOC_UUID \
  --max_alerts 50
```

**Date Range: Alerts from specific day**
```bash
# Get epoch timestamps for January 1, 2024
START_TIME=$(date -d '2024-01-01 00:00:00' +%s)
END_TIME=$(date -d '2024-01-01 23:59:59' +%s)

python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  --alerts \
  --after_time $START_TIME \
  --before_time $END_TIME
```

---

## 🏗️ Implementation Architecture

### 🔄 Alert Mode Process Flow
1. **🔍 Fetch Alerts**: Calls `getPolicyAlerts` API to retrieve policy-triggered alerts
2. **⚡ Process Data**: Extracts timing and device information from each alert
3. **⏰ Calculate Windows**: Determines start/end times with configurable buffer periods
4. **📥 Download Footage**: Uses same video download process as manual mode
5. **📁 Save Files**: Creates alert-specific filenames with metadata

### 🌐 API Endpoints
| Endpoint | Purpose |
|----------|---------|
| `/api/event/getPolicyAlerts` | Retrieve policy alerts |
| `/api/camera/getMinimalCameraStateList` | Get camera states |
| `/api/audiogateway/getMinimalAudioGatewayStateList` | Get audio gateways |
| `/api/camera/getMediaUris` | Get media download URLs |
| `/api/org/generateFederatedSessionToken` | Authentication for downloads |

### ⚡ Performance Features
- **🧵 Multi-threading**: ThreadPoolExecutor with 4 concurrent workers
- **🎯 Smart Processing**: Each camera/alert processed in separate thread
- **⏱️ Rate Limiting**: 0.1s delay between thread starts
- **🔄 Concurrent Downloads**: Multiple alerts downloaded simultaneously

---

## 📁 File Output Patterns

### 📅 Manual Mode Files
```
📁 Manual Mode Output:
├── CameraName_uuid123_1672531200_video.mp4          (video only)
└── CameraName_uuid123_1672531200_videoWithAudio.mp4 (with audio)
```

### 🚨 Alert Mode Files
```
📁 Alert Mode Output:
├── CameraName_uuid123_20240101_143022_alert_motion_alert456_video.mp4    (video only)
└── CameraName_uuid123_20240101_143022_alert_motion_alert456_combined.mp4 (with audio)
```

**📋 Alert Filename Components:**
- `CameraName`: Sanitized camera name
- `uuid123`: Camera UUID
- `20240101_143022`: Alert start time (YYYYMMDD_HHMMSS)
- `motion`: Alert type
- `alert456`: Unique alert identifier

---

## 🛠️ System Requirements

### 📦 Python Dependencies
```txt
requests>=2.25.1
urllib3>=1.26.0
ffmpeg-python>=0.2.0
```

### 💻 System Requirements
- **Python**: 3.6 or higher
- **FFmpeg**: For audio/video processing
- **Disk Space**: Plan for ~50MB per minute of HD footage
- **Network**: Stable connection to Rhombus API

### 📥 Installation Steps

1. **Clone/Download the script**
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Install FFmpeg**:
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # CentOS/RHEL
   sudo yum install ffmpeg
   ```
4. **Get API Key**: Rhombus Console → Settings → API Management
5. **Test installation**:
   ```bash
   python3 copy_footage_script_threading.py --help
   ```

---

## 🐛 Troubleshooting

### ❌ Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| **"No policy alerts found"** | Time filters too restrictive | Check `--after_time` and `--before_time` values |
| **"Alert missing timestamp"** | Malformed alert data | Script auto-skips these, check debug logs |
| **"Failed to retrieve policy alerts"** | API key permissions | Verify API key has event access permissions |
| **FFmpeg errors** | Missing FFmpeg | Install FFmpeg and ensure it's in PATH |
| **"Connection timeout"** | Network issues | Try with `--usewan` flag or check network |

### 🔍 Debug Mode

Enable detailed logging with `--debug`:
```bash
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts --debug
```

**Debug output includes:**
- ✅ API response data
- ✅ Alert processing steps
- ✅ Download progress
- ✅ Detailed error messages
- ✅ Threading information

### 📊 Monitoring Script Health

**Check if script is working:**
```bash
# Test API connection
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts --max_alerts 1 --debug

# Check recent files
ls -la *.mp4 | head -10

# Monitor disk usage
df -h .
```

---

## ⚡ Advanced Configuration

### ⏰ Buffer Time Configuration

The `--alert_buffer` parameter adds context around incidents:

| Buffer Time | Use Case | Example |
|-------------|----------|---------|
| **10-15 seconds** | Quick incidents | Door access, motion detection |
| **30 seconds** (default) | General security events | Most alerts |
| **60-120 seconds** | Complex incidents | Altercations, accidents |
| **300 seconds** (5 min) | Investigation needs | Comprehensive context |

```bash
# Short buffer for motion alerts
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts --alert_buffer 15

# Extended buffer for security incidents
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts --alert_buffer 120
```

### 🕐 Time Filtering Strategies

**Last 4 hours of alerts:**
```bash
python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  --alerts \
  --after_time $(date -d '4 hours ago' +%s)
```

**Business hours only (9 AM - 5 PM yesterday):**
```bash
START=$(date -d 'yesterday 09:00:00' +%s)
END=$(date -d 'yesterday 17:00:00' +%s)

python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  --alerts \
  --after_time $START \
  --before_time $END
```

**Weekend alerts only:**
```bash
# Saturday
SAT_START=$(date -d 'last saturday 00:00:00' +%s)
SAT_END=$(date -d 'last saturday 23:59:59' +%s)

python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  --alerts \
  --after_time $SAT_START \
  --before_time $SAT_END
```

---

## 🚀 Production Deployment

### 📋 Deployment Checklist

- [ ] **Server Setup**: Dedicated server/NAS with adequate storage
- [ ] **Dependencies**: Python 3.6+, FFmpeg, required packages installed
- [ ] **API Access**: Valid API key with proper permissions
- [ ] **Network**: Reliable connection to Rhombus API
- [ ] **Storage**: Monitor disk space and implement rotation
- [ ] **Logging**: Set up log rotation and monitoring
- [ ] **Alerts**: Configure failure notifications

### ⏰ Automated Scheduling

**Hourly alert check (recommended):**
```bash
# Add to crontab: crontab -e
0 * * * * cd /path/to/script && /usr/bin/python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts --after_time $(date -d '1 hour ago' +%s) >> /var/log/rhombus-backup.log 2>&1
```

**Daily full backup:**
```bash
# Add to crontab: crontab -e  
0 2 * * * cd /path/to/script && /usr/bin/python3 copy_footage_script_threading.py -a YOUR_API_KEY -s $(date -d 'yesterday 00:00:00' +%s) -u 86400 >> /var/log/rhombus-backup.log 2>&1
```

**Weekly alert summary:**
```bash
# Add to crontab: crontab -e
0 1 * * 1 cd /path/to/script && /usr/bin/python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts --after_time $(date -d '1 week ago' +%s) --max_alerts 1000 >> /var/log/rhombus-weekly.log 2>&1
```

### 📊 Monitoring & Maintenance

**Log rotation setup:**
```bash
# Create /etc/logrotate.d/rhombus-backup
/var/log/rhombus-*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
}
```

**Disk space monitoring:**
```bash
#!/bin/bash
# disk-check.sh - Add to cron every 6 hours
USAGE=$(df /path/to/storage | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $USAGE -gt 85 ]; then
    echo "WARNING: Disk usage at ${USAGE}%" | mail -s "Storage Alert" admin@company.com
fi
```

**Health check script:**
```bash
#!/bin/bash
# health-check.sh - Add to cron every hour
LOGFILE="/var/log/rhombus-backup.log"
ERRORS=$(tail -100 $LOGFILE | grep -i error | wc -l)
if [ $ERRORS -gt 5 ]; then
    echo "Multiple errors detected in backup script" | mail -s "Backup Alert" admin@company.com
fi
```

---

## 📈 Performance Optimization

### 🔧 Tuning Parameters

**For high-volume environments:**
```bash
# Increase concurrent workers (modify script)
# In copy_footage_script_threading.py, line ~686:
# ThreadPoolExecutor(max_workers=8)  # Increase from 4 to 8

# Process more alerts per run
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts --max_alerts 500
```

**For limited bandwidth:**
```bash
# Use LAN connection when possible (default)
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts

# Reduce buffer time to minimize data
python3 copy_footage_script_threading.py -a YOUR_API_KEY --alerts --alert_buffer 10
```

### 📊 Resource Planning

**Storage estimation:**
- **HD footage**: ~50MB per minute
- **4K footage**: ~150MB per minute  
- **Audio**: ~1MB per minute (additional)

**Example calculation:**
- 100 alerts/day × 2 minutes average × 50MB = **10GB/day**
- Monthly storage need: **~300GB**
- Recommended storage: **1TB** (with rotation)

---

## 🎯 Use Case Scenarios

### 🏢 **Corporate Security**
```bash
# Monitor all locations during business hours
python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  --alerts \
  --after_time $(date -d 'today 08:00:00' +%s) \
  --before_time $(date -d 'today 18:00:00' +%s) \
  --alert_buffer 60
```

### 🏪 **Retail Loss Prevention**
```bash
# High-frequency monitoring for theft prevention
python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  --alerts \
  --max_alerts 1000 \
  --alert_buffer 120
```

### 🏭 **Manufacturing Compliance**
```bash
# Location-specific safety incident documentation
python3 copy_footage_script_threading.py \
  -a YOUR_API_KEY \
  --alerts \
  --location_uuid FACTORY_UUID \
  --alert_buffer 300
```

### 🏠 **Multi-site Management**
```bash
# Process each location separately
for location in LOC1_UUID LOC2_UUID LOC3_UUID; do
    python3 copy_footage_script_threading.py \
      -a YOUR_API_KEY \
      --alerts \
      --location_uuid $location \
      --max_alerts 200
done
```

---

## 📞 Support & Resources

### 🔗 API Documentation
- [Rhombus API Docs](https://apidocs.rhombussystems.com/)
- [Get Locations](https://apidocs.rhombussystems.com/reference/getlocations)
- [Get Camera Config](https://apidocs.rhombussystems.com/reference/getcameraconfig)

### 🛠️ Tools
- [Epoch Converter](https://www.epochconverter.com/) - Convert human time to epoch
- [JSON Formatter](https://jsonformatter.org/) - Format API responses
- [Cron Generator](https://crontab.guru/) - Create cron schedules

### 📧 Getting Help
1. **Enable debug mode**: `--debug` flag
2. **Check logs**: Review error messages
3. **Verify API key**: Test with simple API calls
4. **Contact Rhombus Support**: Include debug logs

---

> 💡 **Pro Tip**: Start with alert mode for automatic incident capture, then use manual mode for specific investigations or scheduled backups. The combination provides comprehensive coverage for security and compliance needs.