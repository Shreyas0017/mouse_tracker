from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import time
import threading
from datetime import datetime
from werkzeug.utils import secure_filename
import io
import base64
from PIL import Image
import uuid
import zipfile
import shutil

app = Flask(__name__)
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
UPLOAD_FOLDER = 'temp_frames'
RESULTS_FOLDER = 'experiments'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Global tracking state
tracking_sessions = {}
active_experiments = {}

# Colors for different mice (BGR format for OpenCV)
MOUSE_COLORS = [
    (0, 255, 0),    # Green
    (255, 0, 0),    # Blue  
    (0, 0, 255),    # Red
    (0, 255, 255),  # Yellow
    (255, 0, 255),  # Magenta
    (255, 255, 0),  # Cyan
    (0, 128, 255),  # Orange
    (128, 0, 128),  # Purple
    (203, 192, 255) # Pink
]

MOVEMENT_THRESHOLD = 2

class TrackingSession:
    def __init__(self, session_id, num_mice, rois, black_white=False):
        self.session_id = session_id
        self.num_mice = num_mice
        self.rois = rois  # List of (x, y, w, h) tuples
        self.black_white = black_white
        self.trackers = []
        self.points = [[] for _ in range(num_mice)]
        self.states = [[] for _ in range(num_mice)]
        self.prev_positions = [None for _ in range(num_mice)]
        self.frame_count = 0
        self.start_time = datetime.now()
        self.experiment_dir = None
        self.video_writer = None
        self.is_initialized = False
        self.lock = threading.Lock()
        
    def initialize_trackers(self, first_frame):
        """Initialize CSRT trackers with the first frame and ROIs"""
        try:
            self.trackers.clear()
            
            for roi in self.rois:
                tracker = cv2.TrackerCSRT_create()
                # Convert ROI from (x, y, w, h) format
                bbox = (roi['x'], roi['y'], roi['width'], roi['height'])
                success = tracker.init(first_frame, bbox)
                if not success:
                    raise Exception(f"Failed to initialize tracker for ROI {bbox}")
                self.trackers.append(tracker)
            
            # Create experiment directory
            timestamp = self.start_time.strftime("%Y-%m-%d_%H-%M-%S")
            self.experiment_dir = os.path.join(RESULTS_FOLDER, f"Experiment_{self.session_id}_{timestamp}")
            os.makedirs(self.experiment_dir, exist_ok=True)
            
            # Initialize video writer
            h, w = first_frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_path = os.path.join(self.experiment_dir, 'tracking_video.mp4')
            self.video_writer = cv2.VideoWriter(video_path, fourcc, 10.0, (w, h))
            
            self.is_initialized = True
            return True
            
        except Exception as e:
            print(f"Error initializing trackers: {e}")
            return False
    
    def process_frame(self, frame):
        """Process a single frame and update tracking"""
        if not self.is_initialized or not self.trackers:
            return None
            
        with self.lock:
            try:
                processed_frame = frame.copy()
                
                # Apply black and white if enabled
                if self.black_white:
                    processed_frame = cv2.cvtColor(cv2.cvtColor(processed_frame, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
                
                # Update each tracker
                for idx, tracker in enumerate(self.trackers):
                    success, box = tracker.update(frame)
                    
                    if success:
                        x, y, w, h = [int(v) for v in box]
                        center = (int(x + w/2), int(y + h/2))
                        
                        # Add point to tracking data
                        self.points[idx].append(center)
                        
                        # Determine movement state
                        if self.prev_positions[idx]:
                            dist = np.linalg.norm(np.array(center) - np.array(self.prev_positions[idx]))
                            state = "Moving" if dist > MOVEMENT_THRESHOLD else "Resting"
                        else:
                            state = "Moving"
                        
                        self.states[idx].append(state)
                        self.prev_positions[idx] = center
                        
                        # Draw tracking visualization
                        color = MOUSE_COLORS[idx % len(MOUSE_COLORS)]
                        
                        # Draw path
                        if len(self.points[idx]) > 1:
                            for j in range(1, len(self.points[idx])):
                                cv2.line(processed_frame, self.points[idx][j-1], self.points[idx][j], color, 2)
                        
                        # Draw current position
                        cv2.circle(processed_frame, center, 5, color, -1)
                        
                        # Draw bounding box
                        cv2.rectangle(processed_frame, (x, y), (x + w, y + h), color, 2)
                        
                        # Draw label
                        label = f"Mouse {idx + 1}: {state}"
                        cv2.putText(processed_frame, label, (x, y - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                # Save frame to video
                if self.video_writer:
                    self.video_writer.write(processed_frame)
                
                self.frame_count += 1
                return processed_frame
                
            except Exception as e:
                print(f"Error processing frame: {e}")
                return None
    
    def stop_tracking(self):
        """Stop tracking and save results"""
        try:
            with self.lock:
                # Release video writer
                if self.video_writer:
                    self.video_writer.release()
                    self.video_writer = None
                
                # Save tracking data
                if self.experiment_dir and any(self.points):
                    self.save_results()
                
                end_time = datetime.now()
                duration = (end_time - self.start_time).total_seconds()
                
                return {
                    'experiment_id': self.session_id,
                    'duration': f"{duration:.2f} seconds",
                    'total_frames': self.frame_count,
                    'experiment_dir': self.experiment_dir
                }
        except Exception as e:
            print(f"Error stopping tracking: {e}")
            return {'error': str(e)}
    
    def save_results(self):
        """Save tracking results to Excel and generate path visualization"""
        try:
            # Save tracking data to Excel
            all_data = []
            for idx in range(self.num_mice):
                if self.points[idx]:  # Only save if we have data
                    df = pd.DataFrame(self.points[idx], columns=['X', 'Y'])
                    df['State'] = self.states[idx]
                    df['Mouse'] = idx + 1
                    df['Frame'] = range(len(self.points[idx]))
                    all_data.append(df)
            
            if all_data:
                final_df = pd.concat(all_data, ignore_index=True)
                excel_path = os.path.join(self.experiment_dir, 'tracking_data.xlsx')
                final_df.to_excel(excel_path, index=False)
            
            # Generate path visualization
            self.generate_path_plot()
            
        except Exception as e:
            print(f"Error saving results: {e}")
    
    def generate_path_plot(self):
        """Generate and save path visualization"""
        try:
            plt.figure(figsize=(12, 8))
            
            for idx in range(self.num_mice):
                if self.points[idx]:  # Only plot if we have data
                    points = np.array(self.points[idx])
                    color = np.array(MOUSE_COLORS[idx % len(MOUSE_COLORS)]) / 255.0
                    # Convert BGR to RGB for matplotlib
                    color = [color[2], color[1], color[0]]
                    
                    plt.plot(points[:, 0], points[:, 1], color=color, 
                           label=f'Mouse {idx + 1}', linewidth=2, alpha=0.8)
                    
                    # Mark start and end points
                    if len(points) > 0:
                        plt.scatter(points[0, 0], points[0, 1], color='green', 
                                  marker='o', s=100, label=f'Start {idx + 1}' if idx == 0 else "")
                        plt.scatter(points[-1, 0], points[-1, 1], color='red', 
                                  marker='X', s=100, label=f'End {idx + 1}' if idx == 0 else "")
            
            plt.gca().invert_yaxis()
            plt.xlabel('X Coordinate')
            plt.ylabel('Y Coordinate')
            plt.title('Mouse Movement Paths')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            plot_path = os.path.join(self.experiment_dir, 'mouse_paths.png')
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            
        except Exception as e:
            print(f"Error generating path plot: {e}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_sessions': len(active_experiments)
    })

@app.route('/start_tracking', methods=['POST'])
def start_tracking():
    """Initialize a new tracking session"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['number_of_mice', 'rois']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        num_mice = data['number_of_mice']
        rois = data['rois']
        black_white = data.get('black_white_mode', False)
        
        # Validate data
        if not isinstance(num_mice, int) or num_mice < 1 or num_mice > 9:
            return jsonify({'error': 'Invalid number of mice (1-9)'}), 400
        
        if len(rois) != num_mice:
            return jsonify({'error': 'Number of ROIs must match number of mice'}), 400
        
        # Generate session ID
        session_id = str(uuid.uuid4())[:8]
        
        # Create tracking session
        session = TrackingSession(session_id, num_mice, rois, black_white)
        tracking_sessions[session_id] = session
        active_experiments[session_id] = session
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Tracking session initialized. Send frames to /process_frame'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/process_frame', methods=['POST'])
def process_frame():
    """Process a single frame for tracking"""
    try:
        if 'frame' not in request.files:
            return jsonify({'error': 'No frame provided'}), 400
        
        if 'session_id' not in request.form:
            return jsonify({'error': 'No session_id provided'}), 400
        
        session_id = request.form['session_id']
        file = request.files['frame']
        
        if session_id not in active_experiments:
            return jsonify({'error': 'Invalid or expired session'}), 400
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        session = active_experiments[session_id]
        
        # Read image from file
        file_bytes = np.frombuffer(file.read(), np.uint8)
        frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Invalid image format'}), 400
        
        # Initialize trackers with first frame
        if not session.is_initialized:
            if not session.initialize_trackers(frame):
                return jsonify({'error': 'Failed to initialize trackers'}), 500
        
        # Process frame
        processed_frame = session.process_frame(frame)
        
        if processed_frame is None:
            return jsonify({'error': 'Frame processing failed'}), 500
        
        return jsonify({
            'success': True,
            'frame_count': session.frame_count,
            'message': 'Frame processed successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stop_tracking', methods=['POST'])
def stop_tracking():
    """Stop tracking and return results"""
    try:
        data = request.get_json()
        
        if not data or 'session_id' not in data:
            return jsonify({'error': 'No session_id provided'}), 400
        
        session_id = data['session_id']
        
        if session_id not in active_experiments:
            return jsonify({'error': 'Invalid or expired session'}), 400
        
        session = active_experiments[session_id]
        results = session.stop_tracking()
        
        # Remove from active experiments but keep in tracking_sessions for potential data access
        del active_experiments[session_id]
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_results/<session_id>', methods=['GET'])
def get_results(session_id):
    """Get results for a specific session"""
    try:
        if session_id not in tracking_sessions:
            return jsonify({'error': 'Session not found'}), 404
        
        session = tracking_sessions[session_id]
        
        if not session.experiment_dir or not os.path.exists(session.experiment_dir):
            return jsonify({'error': 'Results not available'}), 404
        
        # Create a zip file with all results
        zip_path = os.path.join(session.experiment_dir, 'results.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zip_file:
            for root, dirs, files in os.walk(session.experiment_dir):
                for file in files:
                    if file != 'results.zip':  # Don't include the zip file itself
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, session.experiment_dir)
                        zip_file.write(file_path, arcname)
        
        return send_file(zip_path, as_attachment=True, download_name=f'experiment_{session_id}_results.zip')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/list_experiments', methods=['GET'])
def list_experiments():
    """List all experiments"""
    try:
        experiments = []
        
        for session_id, session in tracking_sessions.items():
            experiments.append({
                'session_id': session_id,
                'num_mice': session.num_mice,
                'start_time': session.start_time.isoformat(),
                'frame_count': session.frame_count,
                'is_active': session_id in active_experiments,
                'has_results': session.experiment_dir and os.path.exists(session.experiment_dir)
            })
        
        return jsonify({
            'experiments': experiments,
            'total': len(experiments),
            'active': len(active_experiments)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cleanup', methods=['POST'])
def cleanup_old_sessions():
    """Cleanup old tracking sessions and files"""
    try:
        # Remove sessions older than 24 hours
        current_time = datetime.now()
        old_sessions = []
        
        for session_id, session in tracking_sessions.items():
            age = (current_time - session.start_time).total_seconds() / 3600  # hours
            if age > 24:  # Older than 24 hours
                old_sessions.append(session_id)
        
        # Clean up old sessions
        for session_id in old_sessions:
            session = tracking_sessions[session_id]
            if session.experiment_dir and os.path.exists(session.experiment_dir):
                shutil.rmtree(session.experiment_dir, ignore_errors=True)
            
            del tracking_sessions[session_id]
            if session_id in active_experiments:
                del active_experiments[session_id]
        
        # Clean up temp files
        for file in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, file)
            if os.path.isfile(file_path):
                file_age = (current_time.timestamp() - os.path.getmtime(file_path)) / 3600
                if file_age > 1:  # Older than 1 hour
                    os.remove(file_path)
        
        return jsonify({
            'success': True,
            'cleaned_sessions': len(old_sessions),
            'message': 'Cleanup completed'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create required directories
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    
    # Run the app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)