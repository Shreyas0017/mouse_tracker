# Rat Path Tracker - Advanced Motion Analysis System

A professional GUI application for tracking and analyzing rat movement paths in video footage using computer vision.

## Features

- 🎥 **Video Input**: Support for webcam and video files (MP4, AVI, MOV, MKV)
- 🎯 **Interactive Selection**: Click and drag to select the target
- ▶️ **Real-time Tracking**: CSRT tracker for accurate motion tracking
- 📊 **Live Statistics**: Distance, average speed, and path points
- 💾 **Export Options**: Save path data as CSV and images as PNG
- 🎨 **Modern UI**: Clean, professional interface with dark theme
- 📈 **Automatic Summary**: End-of-video dialog with save options

## Installation

### Prerequisites
- Python 3.8 or higher
- Windows/Linux/macOS

### Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
```

2. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the application:
```bash
python fresh.py
```

### Workflow

1. **Load Video Source**
   - Click "🎥 Use Webcam" for live camera feed
   - Click "📁 Load Video File" to open a video file

2. **Select Target**
   - Click "🎯 Select Target"
   - Click and drag on the video to draw a box around the rat
   - Release to confirm selection

3. **Start Tracking**
   - Click "▶️ Start" to begin tracking
   - The path will be drawn in cyan color
   - Live statistics update in the top bar

4. **Control Tracking**
   - Click "⏹️ Stop" to pause tracking
   - Click "🗑️ Clear Path" to reset the recorded path

5. **Save Results**
   - When video ends, a summary dialog appears automatically
   - Click "Save Path (CSV)" to export coordinates
   - Click "Save Image (PNG)" to save the final frame with path overlay

## Keyboard Shortcuts

- **ESC**: Cancel current selection

## Output Formats

### CSV Format
Contains path coordinates:
```
index,x,y
0,320,240
1,322,242
...
```

### PNG Image
Final video frame with complete path overlay and position markers.

## Technical Details

- **Tracker**: OpenCV CSRT (Discriminative Correlation Filter with Channel and Spatial Reliability)
- **Path Rendering**: Solid cyan lines with position markers
- **Thread-safe**: Video processing runs in separate thread
- **Auto-scaling**: Window adapts to 90% of screen size

## Requirements

- opencv-python >= 4.8.0
- numpy >= 1.24.0
- Pillow >= 10.0.0

## Troubleshooting

**Issue**: Buttons appear cut off
- The app auto-scales to 90% of your screen
- Minimum recommended resolution: 1280x720

**Issue**: Tracking lost
- Try re-selecting the target with a larger bounding box
- Ensure good lighting and contrast
- Avoid rapid movements or occlusions

**Issue**: Webcam not detected
- Check camera permissions in system settings
- Try closing other applications using the camera
- Verify camera is properly connected

## License

MIT License - Free to use and modify

## Author

Created with ❤️ for motion tracking research
