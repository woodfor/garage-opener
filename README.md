# Garage Opener - License Plate Recognition System

An automated garage door opener system that uses computer vision to detect and recognize license plates from an RTSP camera stream. When a whitelisted license plate is detected, the system automatically opens the garage door using a Meross MSG100 garage door opener.

## Hardware Requirements

### Required Hardware

1. **Meross MSG100 Garage Door Opener** (or compatible Meross garage door opener)
   - This project is specifically designed to work with the Meross MSG100 garage door opener
   - If you use a different garage door opener brand or model, you will need to write custom driver software to replace the `MerossGarageController` class in `meross_controller.py`
   - The MSG100 connects to your garage door opener and can be controlled via Wi-Fi through the Meross cloud API

2. **IP Camera with RTSP Support**
   - Any camera that supports RTSP (Real-Time Streaming Protocol)
   - The camera should be positioned to capture license plates of vehicles approaching the garage
   - Must be accessible on your network

3. **Computer/Raspberry Pi**
   - **Python 3.13.2 is required**
   - Should have sufficient processing power for YOLO models and license plate recognition
   - GPU recommended but not required (CPU inference is supported)

### Model Files Required

- `yolov8n.pt` - YOLOv8 nano model for vehicle detection (automatically downloaded on first use)
- `license_plate_detector.pt` - Custom YOLO model for license plate detection (must be provided)

## Setup

### Prerequisites

- **Python 3.13.2** must be installed on your system

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root directory (note: the project uses `.env`, not `.env.local`).

Add the following environment variables to your `.env` file:

```env
# Meross Cloud Account Credentials
MEROSS_EMAIL=your_meross_account_email@example.com
MEROSS_PASSWORD=your_meross_account_password
MEROSS_GARAGE_DOOR_NAME=Your_Garage_Door_Device_Name

# RTSP Camera Stream URL
RTSP_URL=rtsp://username:password@camera_ip_address:port/stream_path

# Optional: Fast Plate OCR Model (defaults to "cct-xs-v1-global-model" if not set)
FAST_PLATE_OCR_MODEL=cct-xs-v1-global-model
```

#### Environment Variable Details

- **MEROSS_EMAIL**: Your Meross cloud account email address used to authenticate with the Meross API
- **MEROSS_PASSWORD**: Your Meross cloud account password
- **MEROSS_GARAGE_DOOR_NAME**: The exact device name of your MSG100 garage door opener as it appears in the Meross app. This must match exactly (case-sensitive).
- **RTSP_URL**: See RTSP_URL section below for detailed explanation
- **FAST_PLATE_OCR_MODEL**: Optional. Specifies which OCR model to use for license plate recognition. Defaults to `cct-xs-v1-global-model` if not specified.

### 3. RTSP_URL Configuration

**What is RTSP_URL?**

RTSP (Real-Time Streaming Protocol) is a network protocol used for streaming video. The `RTSP_URL` environment variable contains the connection string to your IP camera's video stream.

**Format:**
```
rtsp://[username]:[password]@[camera_ip]:[port]/[stream_path]
```

**Examples:**

1. **Basic RTSP URL (no authentication):**
   ```
   RTSP_URL=rtsp://192.168.1.100:554/stream1
   ```

2. **RTSP URL with username and password:**
   ```
   RTSP_URL=rtsp://admin:mypassword@192.168.1.100:554/stream1
   ```

3. **RTSP URL with specific stream path (common for cameras with multiple streams):**
   ```
   RTSP_URL=rtsp://admin:password@192.168.1.100:554/h264Preview_01_main
   ```

**How to find your RTSP URL:**

1. Check your camera's documentation or admin interface for RTSP settings
2. Common RTSP ports: 554 (default), 8554
3. Many camera manufacturers provide RTSP URLs in their setup documentation
4. You can test the RTSP URL using VLC Media Player: Open Network Stream → enter the RTSP URL

**Important:** Make sure your camera and the computer running this script are on the same network, and that firewall rules allow RTSP traffic.

### 4. License Plate Whitelist Configuration

**Why update the license_plate_whitelist?**

The `license_plate_whitelist` in `main.py` (line 30) contains the list of license plate numbers that are authorized to automatically open the garage door. Only vehicles with license plates matching entries in this whitelist will trigger the door opening mechanism.

**Security Note:** This is a security-critical list. Only add license plates you trust. Anyone with a matching license plate will be able to automatically open your garage door.

**How to update:**

Edit `main.py` and modify the `license_plate_whitelist` variable:

```python
license_plate_whitelist = ["1SB3HM", "ABC123", "XYZ789"]
```

The system uses fuzzy matching (80% similarity threshold) to handle OCR errors, so slight misreads will still match if they're close enough. The similarity threshold can be adjusted in the `is_string_similar_to_any_in_list()` function call (line 188).

**Example:** If your license plate is "ABC123", entries like "ABC-123", "ABC 123", or "ABC12" (due to OCR errors) may still match.

## Configuration Parameters

### LPR_PROCESSING_INTERVAL

**Location:** `main.py` line 21

**What is LPR_PROCESSING_INTERVAL?**

`LPR_PROCESSING_INTERVAL` determines how frequently (in seconds) the system processes frames from the camera stream for license plate recognition.

- **Current setting:** 10 seconds
- **Meaning:** The system will analyze every 10th second worth of frames for vehicles and license plates
- **Why:** License plate recognition is computationally expensive. Processing every frame would be unnecessary and could overwhelm the system. This interval ensures the system captures vehicles that approach while maintaining reasonable performance.

**Adjusting the interval:**

- **Lower values (e.g., 5 seconds):** More frequent detection, higher CPU/GPU usage, better chance of catching fast-moving vehicles
- **Higher values (e.g., 20 seconds):** Less frequent detection, lower resource usage, might miss some vehicles if they pass quickly

**Example:**
```python
LPR_PROCESSING_INTERVAL = 5  # Process every 5 seconds (more frequent)
LPR_PROCESSING_INTERVAL = 20  # Process every 20 seconds (less frequent)
```

### Frame Rotation

The frame rotation in `main.py` line 255 is specific to the current camera's orientation. Frames are rotated 90 degrees clockwise to make the license plate horizontal for detection. If your camera already outputs a correctly oriented image (horizontal), you can remove or change this rotation.

Code reference:
```254:256:/home/jet/Projects/garage-opener/main.py
            if (
                current_time_monotonic - last_lpr_processed_time
            ) >= LPR_PROCESSING_INTERVAL:
                # rotate the frame 90 degrees
                frame_rotated = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
```

- If your feed is already horizontal: remove the rotation and use `frame` directly.
- If your feed is upside down: change to `cv2.ROTATE_180`.
- If your feed is rotated the other way: use `cv2.ROTATE_90_COUNTERCLOCKWISE`.

## Running the System

```bash
python main.py
```

The system will:
1. Connect to the RTSP camera stream
2. Periodically process frames for vehicle and license plate detection
3. When a whitelisted license plate is detected, automatically open the garage door
4. Log all detection events and door operations to `log.csv`
5. Save thresholded license plate images to `license_plate_crops_thresh/` when a match is found

## Output Files

- **log.csv**: Timestamped log of all license plate detections and door operations
- **log.txt**: Error log for debugging
- **license_plate_crops_thresh/**: Directory containing processed license plate images (saved when whitelisted plates are detected)

## Troubleshooting

1. **"Cannot open RTSP stream"**: 
   - Verify the RTSP_URL is correct and accessible
   - Test the URL in VLC Media Player
   - Check firewall settings

2. **"Cannot find garage door device"**:
   - Verify MEROSS_GARAGE_DOOR_NAME matches the device name in your Meross app exactly (case-sensitive)
   - Ensure the MSG100 is online and connected to your Wi-Fi

3. **"No license plates detected"**:
   - Check camera positioning and angle
   - Verify lighting conditions are adequate
   - Ensure the `license_plate_detector.pt` model file is present and valid

4. **Door not opening**:
   - Check the cooldown period (default 120 seconds between opens)
   - Verify Meross credentials are correct
   - Check `log.txt` for error messages

## Architecture

- **main.py**: Main application loop, handles RTSP stream, frame processing, and orchestration
- **meross_controller.py**: Meross MSG100 garage door opener control interface
- **util.py**: License plate OCR and utility functions

## License

See project license file.

