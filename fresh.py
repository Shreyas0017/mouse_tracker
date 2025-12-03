import cv2
import numpy as np
from collections import deque
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import threading
import time
import math

class RatTrackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Rat Path Tracker - Advanced Tracking System")
        
        # Get screen dimensions and set reasonable size
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Use 90% of screen size or max 1400x800
        window_width = min(int(screen_width * 0.9), 1400)
        window_height = min(int(screen_height * 0.85), 800)
        
        # Center the window
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.configure(bg='#0f0f1e')
        
        # Color scheme
        self.colors = {
            'bg_dark': '#0f0f1e',
            'bg_medium': '#1a1a2e',
            'bg_light': '#16213e',
            'accent_primary': '#00d4ff',
            'accent_secondary': '#7d3cff',
            'accent_success': '#00ff88',
            'accent_warning': '#ffaa00',
            'accent_danger': '#ff3366',
            'text_primary': '#ffffff',
            'text_secondary': '#a0a0b8',
            'border': '#2a2a4e'
        }
        
        # Tracking variables
        self.cap = None
        self.video_source = None
        self.is_webcam = False  # Track if using webcam
        self.camera_index = 0  # Default camera index
        self.current_frame = None
        self.original_frame = None
        self.is_selecting = False
        self.selection_start = None
        self.selection_end = None
        self.temp_bbox = None
        
        # Multi-mouse tracking
        self.num_mice = 1  # Number of mice to track
        self.current_mouse_index = 0  # Currently being selected/tracked
        self.mice = []  # List of mouse tracking data
        self.is_tracking = False
        
        # Thread control
        self.stop_thread = False
        self.tracking_thread = None
        self.preview_paused = True
        self.frame_count = 0
        
        # Video timing
        self.fps = None
        self.frame_interval = 0.033
        
        # Colors for different mice
        self.mouse_colors = [
            (0, 255, 0),    # Green
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (255, 255, 0),  # Yellow
            (255, 128, 0),  # Orange
            (128, 0, 255),  # Purple
            (0, 128, 255),  # Light Blue
            (255, 0, 128),  # Pink
        ]
        
        self.setup_ui()
        
    def create_gradient_button(self, parent, text, command, color1, color2, state=tk.NORMAL):
        """Create a stylish button"""
        btn = tk.Button(parent, text=text, command=command,
                       font=('Segoe UI', 9, 'bold'),
                       bg=color1, fg='white',
                       activebackground=color2, activeforeground='white',
                       relief=tk.FLAT, bd=0,
                       padx=6, pady=5,
                       cursor='hand2',
                       state=state)
        
        # Hover effects
        def on_enter(e):
            if btn['state'] == tk.NORMAL:
                btn.config(bg=color2)
        
        def on_leave(e):
            if btn['state'] == tk.NORMAL:
                btn.config(bg=color1)
        
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        return btn
        
    def update_button_state(self, button, state):
        """Update button state"""
        try:
            button.config(state=state)
            if state == tk.DISABLED:
                button.config(bg='#555555')
            else:
                # Restore original color based on button
                pass
        except:
            pass

        
    def setup_ui(self):
        # Main container with gradient background
        main_container = tk.Frame(self.root, bg=self.colors['bg_dark'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Top bar with app title and stats
        top_bar = tk.Frame(main_container, bg=self.colors['bg_medium'], height=80)
        top_bar.pack(fill=tk.X, pady=(0, 10))
        top_bar.pack_propagate(False)
        
        # App icon and title
        title_frame = tk.Frame(top_bar, bg=self.colors['bg_medium'])
        title_frame.pack(side=tk.LEFT, padx=15, pady=10)
        
        title_label = tk.Label(title_frame, text="🐀 Rat Path Tracker", 
                               font=('Segoe UI', 18, 'bold'), 
                               bg=self.colors['bg_medium'], 
                               fg=self.colors['accent_primary'])
        title_label.pack(side=tk.LEFT)
        
        subtitle_label = tk.Label(title_frame, text="  Motion Analysis", 
                                 font=('Segoe UI', 10), 
                                 bg=self.colors['bg_medium'], 
                                 fg=self.colors['text_secondary'])
        subtitle_label.pack(side=tk.LEFT, padx=(8, 0))
        
        # Stats display in top bar
        stats_frame = tk.Frame(top_bar, bg=self.colors['bg_medium'])
        stats_frame.pack(side=tk.RIGHT, padx=15, pady=8)
        
        # Mice count stat
        mice_frame = self.create_stat_card(stats_frame, "Mice", "0/0", 
                                          self.colors['accent_primary'])
        mice_frame.pack(side=tk.LEFT, padx=4)
        self.mice_count_label = mice_frame.value_label
        
        # Distance stat (total)
        dist_frame = self.create_stat_card(stats_frame, "Total Dist", "0.0 px", 
                                          self.colors['accent_success'])
        dist_frame.pack(side=tk.LEFT, padx=4)
        self.distance_label = dist_frame.value_label
        
        # Speed stat (average across all mice)
        speed_frame = self.create_stat_card(stats_frame, "Avg Speed", "0.0 px/s", 
                                           self.colors['accent_warning'])
        speed_frame.pack(side=tk.LEFT, padx=4)
        self.speed_label = speed_frame.value_label

        # Max speed stat (highest across all mice)
        max_frame = self.create_stat_card(stats_frame, "Max Speed", "0.0 px/s",
                          self.colors['accent_danger'])
        max_frame.pack(side=tk.LEFT, padx=4)
        self.max_speed_label = max_frame.value_label
        
        # Content area
        content_container = tk.Frame(main_container, bg=self.colors['bg_dark'])
        content_container.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Controls
        left_panel = tk.Frame(content_container, bg=self.colors['bg_medium'], width=280)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Add scrollable frame for controls if needed
        canvas_scroll = tk.Canvas(left_panel, bg=self.colors['bg_medium'], highlightthickness=0)
        scrollbar = tk.Scrollbar(left_panel, orient="vertical", command=canvas_scroll.yview)
        scrollable_frame = tk.Frame(canvas_scroll, bg=self.colors['bg_medium'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all"))
        )
        
        canvas_scroll.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        
        canvas_scroll.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add some padding
        inner_left = tk.Frame(scrollable_frame, bg=self.colors['bg_medium'])
        inner_left.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # Video Source Section
        source_frame = self.create_section_frame(inner_left, "📹 Video Source")
        source_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.webcam_btn = self.create_gradient_button(
            source_frame.content, "🎥 Use Webcam", self.use_webcam,
            self.colors['accent_primary'], self.colors['accent_primary']
        )
        self.webcam_btn.pack(fill=tk.X, pady=2)
        
        self.camera_select_btn = self.create_gradient_button(
            source_frame.content, "📷 Select Camera", self.select_camera,
            '#9C27B0', '#9C27B0'
        )
        self.camera_select_btn.pack(fill=tk.X, pady=2)
        
        self.video_btn = self.create_gradient_button(
            source_frame.content, "📁 Load Video File", self.load_video,
            self.colors['accent_secondary'], self.colors['accent_secondary']
        )
        self.video_btn.pack(fill=tk.X, pady=2)
        
        # Mice Configuration Section
        mice_config_frame = self.create_section_frame(inner_left, "🐭 Mice Configuration")
        mice_config_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Number of mice selector
        num_mice_frame = tk.Frame(mice_config_frame.content, bg=self.colors['bg_light'])
        num_mice_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(num_mice_frame, text="Number of Mice", 
                bg=self.colors['bg_light'], fg=self.colors['text_primary'], 
                font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(5, 0))
        
        self.num_mice_var = tk.IntVar(value=1)
        num_mice_value_label = tk.Label(num_mice_frame, text="1", 
                                       bg=self.colors['bg_light'], 
                                       fg=self.colors['accent_primary'],
                                       font=('Segoe UI', 10, 'bold'))
        num_mice_value_label.pack(anchor=tk.E)
        
        self.num_mice_scale = ttk.Scale(num_mice_frame, from_=1, to=8,
                                       orient=tk.HORIZONTAL, 
                                       variable=self.num_mice_var,
                                       style="Custom.Horizontal.TScale",
                                       command=lambda v: self.update_num_mice(v, num_mice_value_label))
        self.num_mice_scale.pack(fill=tk.X, pady=5)
        
        # Current selection status
        self.selection_status_label = tk.Label(mice_config_frame.content, 
                                              text="Ready to configure", 
                                              bg=self.colors['bg_light'], 
                                              fg=self.colors['text_secondary'],
                                              font=('Segoe UI', 9),
                                              wraplength=240)
        self.selection_status_label.pack(fill=tk.X, pady=(5, 0))
        
        # Tracking Controls Section
        # Tracking Controls Section
        control_frame = self.create_section_frame(inner_left, "🎯 Tracking Controls")
        control_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.select_btn = self.create_gradient_button(
            control_frame.content, "🎯 Select Mouse 1", self.start_selection,
            self.colors['accent_success'], self.colors['accent_success'], tk.DISABLED
        )
        self.select_btn.pack(fill=tk.X, pady=3)
        
        # Button row for Start and Stop
        btn_row = tk.Frame(control_frame.content, bg=self.colors['bg_light'])
        btn_row.pack(fill=tk.X, pady=3)
        
        self.track_btn = self.create_gradient_button(
            btn_row, "▶️ Start", self.start_tracking,
            self.colors['accent_success'], self.colors['accent_success'], tk.DISABLED
        )
        self.track_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        
        self.stop_btn = self.create_gradient_button(
            btn_row, "⏸️ Pause", self.stop_tracking,
            self.colors['accent_danger'], self.colors['accent_danger'], tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))
        
        # Data management buttons
        data_row = tk.Frame(control_frame.content, bg=self.colors['bg_light'])
        data_row.pack(fill=tk.X, pady=3)
        
        self.clear_btn = self.create_gradient_button(
            data_row, "🗑️ Clear Data", self.clear_path,
            '#ff8800', '#ff8800'
        )
        self.clear_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        
        # Stop Recording button (only for webcam)
        self.stop_recording_btn = self.create_gradient_button(
            data_row, "⏹️ Stop Recording", self.stop_recording,
            '#cc0000', '#cc0000', tk.DISABLED
        )
        self.stop_recording_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))
        
        # Settings Section
        settings_frame = self.create_section_frame(inner_left, "⚙️ Settings")
        settings_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Path points slider
        points_slider_frame = tk.Frame(settings_frame.content, bg=self.colors['bg_light'])
        points_slider_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(points_slider_frame, text="Max Path Points", 
                bg=self.colors['bg_light'], fg=self.colors['text_primary'], 
                font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(5, 0))
        
        self.max_points_var = tk.IntVar(value=1000)
        points_value_label = tk.Label(points_slider_frame, text="1000", 
                                     bg=self.colors['bg_light'], 
                                     fg=self.colors['accent_primary'],
                                     font=('Segoe UI', 10, 'bold'))
        points_value_label.pack(anchor=tk.E)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.Horizontal.TScale", 
                       background=self.colors['bg_light'],
                       troughcolor=self.colors['bg_dark'],
                       borderwidth=0,
                       lightcolor=self.colors['accent_primary'],
                       darkcolor=self.colors['accent_primary'])
        
        self.max_points_scale = ttk.Scale(points_slider_frame, from_=100, to=5000,
                                         orient=tk.HORIZONTAL, 
                                         variable=self.max_points_var,
                                         style="Custom.Horizontal.TScale",
                                         command=lambda v: self.update_max_points(v, points_value_label))
        self.max_points_scale.pack(fill=tk.X, pady=5)
        
        # Info Section with status
        info_frame = self.create_section_frame(inner_left, "ℹ️ Status")
        info_frame.pack(fill=tk.X, pady=(0, 8))
        
        status_container = tk.Frame(info_frame.content, bg=self.colors['bg_light'])
        status_container.pack(fill=tk.X, pady=5)
        
        self.status_label = tk.Label(status_container, text="⚪ No video loaded", 
                                     bg=self.colors['bg_light'], 
                                     fg=self.colors['text_secondary'], 
                                     font=('Segoe UI', 10),
                                     wraplength=240, justify=tk.LEFT, anchor=tk.W)
        self.status_label.pack(fill=tk.X, padx=10, pady=10)
        
        # Right panel - Video Display with modern styling
        right_panel = tk.Frame(content_container, bg=self.colors['bg_medium'], 
                              highlightthickness=2, highlightbackground=self.colors['border'])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Video header
        video_header = tk.Frame(right_panel, bg=self.colors['bg_light'], height=50)
        video_header.pack(fill=tk.X)
        video_header.pack_propagate(False)
        
        video_title = tk.Label(video_header, text="📺 Live Preview", 
                              font=('Segoe UI', 14, 'bold'), 
                              bg=self.colors['bg_light'], 
                              fg=self.colors['text_primary'])
        video_title.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.points_label = tk.Label(video_header, text="Path: 0 points", 
                                     font=('Segoe UI', 10), 
                                     bg=self.colors['bg_light'], 
                                     fg=self.colors['accent_primary'])
        self.points_label.pack(side=tk.RIGHT, padx=20)
        
        # Video canvas with border
        canvas_container = tk.Frame(right_panel, bg=self.colors['bg_dark'])
        canvas_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.canvas = tk.Canvas(canvas_container, bg='#000000', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events for selection
        self.canvas.bind('<Button-1>', self.on_mouse_down)
        self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)
        
        # Display placeholder
        self.show_placeholder()
    
    def create_section_frame(self, parent, title):
        """Create a modern section frame"""
        outer_frame = tk.Frame(parent, bg=self.colors['bg_medium'])
        
        frame = tk.Frame(outer_frame, bg=self.colors['bg_light'], 
                        highlightthickness=1, highlightbackground=self.colors['border'])
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(frame, text=title, 
                              font=('Segoe UI', 12, 'bold'),
                              bg=self.colors['bg_light'], 
                              fg=self.colors['text_primary'])
        title_label.pack(anchor=tk.W, padx=15, pady=(15, 10))
        
        # Content area
        content = tk.Frame(frame, bg=self.colors['bg_light'])
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Store content reference in outer frame
        outer_frame.content = content
        
        return outer_frame
    
    def create_stat_card(self, parent, label, value, color):
        """Create a stat card for the top bar"""
        card = tk.Frame(parent, bg=self.colors['bg_light'], 
                       highlightthickness=1, highlightbackground=color)
        
        label_widget = tk.Label(card, text=label, 
                               font=('Segoe UI', 9), 
                               bg=self.colors['bg_light'], 
                               fg=self.colors['text_secondary'])
        label_widget.pack(padx=10, pady=(6, 2))
        
        value_label = tk.Label(card, text=value, 
                              font=('Segoe UI', 11, 'bold'), 
                              bg=self.colors['bg_light'], 
                              fg=color)
        value_label.pack(padx=10, pady=(2, 6))
        
        card.value_label = value_label
        return card

        
    def show_placeholder(self):
        """Show modern placeholder when no video is loaded"""
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width > 1:
            # Gradient background effect
            self.canvas.create_rectangle(0, 0, width, height, fill='#000000', outline='')
            
            # Icon
            self.canvas.create_text(width//2, height//2 - 40, 
                                   text="📹", 
                                   fill=self.colors['accent_primary'], 
                                   font=('Segoe UI', 60))
            
            # Main text
            self.canvas.create_text(width//2, height//2 + 30, 
                                   text="Load a video source to begin tracking", 
                                   fill=self.colors['text_secondary'], 
                                   font=('Segoe UI', 16))
            
            # Subtitle
            self.canvas.create_text(width//2, height//2 + 60, 
                                   text="Select a webcam or video file from the controls", 
                                   fill=self.colors['text_secondary'], 
                                   font=('Segoe UI', 11))

    def detect_cameras(self):
        """Detect available cameras"""
        available_cameras = []
        # Test camera indices 0-9
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
                cap.release()
        return available_cameras
    
    def select_camera(self):
        """Open dialog to select camera"""
        available_cameras = self.detect_cameras()
        
        if not available_cameras:
            messagebox.showerror("Error", "No cameras detected!")
            return
        
        # Create camera selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Camera")
        dialog.geometry("300x200")
        dialog.configure(bg=self.colors['bg_dark'])
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="Select Camera:", 
                bg=self.colors['bg_dark'], 
                fg=self.colors['text_primary'],
                font=('Segoe UI', 12, 'bold')).pack(pady=20)
        
        # Create buttons for each camera
        for cam_idx in available_cameras:
            btn = tk.Button(dialog, 
                          text=f"Camera {cam_idx}", 
                          command=lambda idx=cam_idx: self.set_camera(idx, dialog),
                          font=('Segoe UI', 10),
                          bg=self.colors['accent_primary'], 
                          fg='white',
                          activebackground=self.colors['accent_primary'],
                          relief=tk.FLAT,
                          padx=20, pady=10,
                          cursor='hand2')
            btn.pack(fill=tk.X, padx=30, pady=5)
    
    def set_camera(self, camera_index, dialog):
        """Set the selected camera index"""
        self.camera_index = camera_index
        dialog.destroy()
        messagebox.showinfo("Camera Selected", f"Camera {camera_index} selected!\nClick 'Use Webcam' to start.")
    
    def use_webcam(self):
        """Initialize webcam"""
        self.stop_video()
        self.cap = cv2.VideoCapture(self.camera_index)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.video_source = self.camera_index
            self.is_webcam = True
            # determine FPS for consistent playback
            try:
                fps = float(self.cap.get(cv2.CAP_PROP_FPS))
            except Exception:
                fps = 0.0
            if not fps or fps <= 0:
                fps = 30.0
            self.fps = fps
            self.frame_interval = 1.0 / self.fps
            self.status_label.config(text="🟢 Webcam connected and ready", 
                                    fg=self.colors['accent_success'])
            self.update_button_state(self.select_btn, tk.NORMAL)
            self.preview_paused = True
            self.start_video_display()
        else:
            messagebox.showerror("Error", "Could not access webcam")
    
    def load_video(self):
        """Load video file"""
        filename = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if filename:
            self.stop_video()
            self.cap = cv2.VideoCapture(filename)
            if self.cap.isOpened():
                self.video_source = filename
                self.is_webcam = False
                # read FPS from file to keep playback speed correct
                try:
                    fps = float(self.cap.get(cv2.CAP_PROP_FPS))
                except Exception:
                    fps = 0.0
                if not fps or fps <= 0:
                    fps = 30.0
                self.fps = fps
                self.frame_interval = 1.0 / self.fps
                video_name = filename.split('/')[-1] if '/' in filename else filename.split('\\')[-1]
                self.status_label.config(text=f"🟢 Video loaded: {video_name[:30]}...", 
                                        fg=self.colors['accent_success'])
                self.update_button_state(self.select_btn, tk.NORMAL)
                self.preview_paused = True
                self.start_video_display()
            else:
                messagebox.showerror("Error", "Could not load video file")
    
    def start_video_display(self):
        """Start displaying video frames"""
        self.stop_thread = False
        self.tracking_thread = threading.Thread(target=self.video_loop, daemon=True)
        self.tracking_thread.start()
    
    def video_loop(self):
        """Main video display loop with multi-mouse tracking"""
        while not self.stop_thread and self.cap is not None and self.cap.isOpened():
            loop_start = time.time()
            should_fetch_frame = not self.preview_paused or self.original_frame is None
            frame_capture_time = None

            if should_fetch_frame:
                ret, frame = self.cap.read()
                frame_capture_time = time.time()
                if not ret:
                    if isinstance(self.video_source, str):
                        try:
                            self.root.after(0, self.handle_video_end_ui)
                        except Exception:
                            pass
                        break
                    else:
                        break
                self.original_frame = frame.copy()
                self.frame_count += 1

            if self.original_frame is None:
                time.sleep(0.03)
                continue

            self.current_frame = self.original_frame.copy()

            # Track all mice if tracking is active
            if self.is_tracking:
                for mouse_data in self.mice:
                    if mouse_data['tracker'] is None:
                        continue
                    
                    if mouse_data['start_time'] is None:
                        mouse_data['start_time'] = time.time()

                    success, bbox = mouse_data['tracker'].update(self.original_frame)
                    if success:
                        mouse_data['bbox'] = bbox
                        center_x = int(bbox[0] + bbox[2] / 2)
                        center_y = int(bbox[1] + bbox[3] / 2)
                        current_point = (center_x, center_y)

                        # Calculate distance and speed
                        if mouse_data['path_points']:
                            prev_point = mouse_data['path_points'][-1]
                            distance = math.hypot(current_point[0] - prev_point[0], current_point[1] - prev_point[1])
                            mouse_data['total_distance'] += distance

                            # Instantaneous speed
                            now = frame_capture_time if frame_capture_time else time.time()
                            if mouse_data['prev_time']:
                                dt = now - mouse_data['prev_time']
                            else:
                                dt = self.frame_interval
                            if dt <= 0:
                                dt = self.frame_interval
                            
                            inst_speed = distance / dt
                            mouse_data['current_speed'] = inst_speed
                            if inst_speed > mouse_data['highest_speed']:
                                mouse_data['highest_speed'] = inst_speed

                        mouse_data['prev_time'] = frame_capture_time if frame_capture_time else time.time()
                        mouse_data['path_points'].append(current_point)

                        # Average speed
                        if mouse_data['start_time'] and len(mouse_data['path_points']) > 1:
                            elapsed = time.time() - mouse_data['start_time']
                            if elapsed > 0:
                                mouse_data['avg_speed'] = mouse_data['total_distance'] / elapsed

                        # Draw bounding box with mouse color
                        p1 = (int(bbox[0]), int(bbox[1]))
                        p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                        color = mouse_data['color']

                        # Outer glow
                        cv2.rectangle(self.current_frame, (p1[0]-2, p1[1]-2), (p2[0]+2, p2[1]+2), color, 1)
                        # Main box
                        cv2.rectangle(self.current_frame, p1, p2, color, 3)

                        # Label
                        label = f"Mouse {mouse_data['id']}"
                        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                        cv2.rectangle(self.current_frame, (p1[0], p1[1] - label_size[1] - 12), (p1[0] + label_size[0] + 8, p1[1]), color, -1)
                        cv2.putText(self.current_frame, label, (p1[0] + 4, p1[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                    else:
                        # Tracking lost
                        mouse_data['current_speed'] = 0.0
                        mouse_data['prev_time'] = None

            # Draw all paths
            self.draw_all_paths(self.current_frame)

            # Draw temporary selection box
            if self.is_selecting and self.temp_bbox:
                x, y, w, h = self.temp_bbox
                # Use color for current mouse being selected
                sel_color = self.mouse_colors[self.current_mouse_index % len(self.mouse_colors)]
                cv2.rectangle(self.current_frame, (x, y), (x+w, y+h), sel_color, 3)
                cv2.rectangle(self.current_frame, (x-2, y-2), (x+w+2, y+h+2), (255, 255, 255), 1)
                label_text = f"Mouse {self.current_mouse_index + 1} - Release to confirm"
                label_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(self.current_frame, (x, y - label_size[1] - 15), (x + label_size[0] + 10, y), sel_color, -1)
                cv2.putText(self.current_frame, label_text, (x + 5, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

            # Draw aggregate stats overlay
            try:
                self.draw_aggregate_stats(self.current_frame)
            except Exception:
                pass

            # Update display
            self.display_frame(self.current_frame)

            # Update UI statistics
            self.update_aggregate_ui_stats()

            # Sleep to respect video FPS
            if should_fetch_frame and self.fps and self.fps > 0:
                elapsed = time.time() - loop_start
                remaining = self.frame_interval - elapsed
                if remaining > 0:
                    time.sleep(remaining)
            else:
                time.sleep(0.03)

    def handle_video_end_ui(self):
        """Run on the main thread when a video file ends: stop tracking and show save dialog"""
        # Stop tracking and preview
        self.is_tracking = False
        self.preview_paused = True
        self.stop_thread = True

        # Update buttons and status
        try:
            self.update_button_state(self.select_btn, tk.DISABLED)
            self.update_button_state(self.track_btn, tk.DISABLED)
            self.update_button_state(self.stop_btn, tk.DISABLED)
        except Exception:
            pass

        self.status_label.config(text="⚪ Video ended — recording complete", fg=self.colors['text_secondary'])

        # Show a summary / save dialog
        self.show_save_summary()

    def show_save_summary(self):
        """Display a small window summarizing the recorded paths and allow saving"""
        if not self.original_frame is None:
            preview_img = self.original_frame.copy()
        else:
            preview_img = None

        # Draw all recorded paths onto a copy for preview
        if preview_img is not None and self.mice:
            self.draw_all_paths(preview_img)

        win = tk.Toplevel(self.root)
        win.title("Recording Complete — Save Paths")
        win.configure(bg=self.colors['bg_medium'])
        win.geometry("700x580")

        # Preview area
        preview_frame = tk.Frame(win, bg=self.colors['bg_light'])
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if preview_img is not None:
            # convert to PIL image for display
            img_rgb = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(img_rgb)
            pil.thumbnail((660, 360))
            imgtk = ImageTk.PhotoImage(pil)
            img_label = tk.Label(preview_frame, image=imgtk, bg=self.colors['bg_light'])
            img_label.image = imgtk
            img_label.pack(padx=5, pady=5)
        else:
            tk.Label(preview_frame, text="No frame available for preview", bg=self.colors['bg_light'], fg=self.colors['text_secondary']).pack(padx=10, pady=10)

        # Stats and buttons
        bottom = tk.Frame(win, bg=self.colors['bg_medium'])
        bottom.pack(fill=tk.X, padx=10, pady=(0,10))

        # Aggregate stats
        total_dist = sum(m['total_distance'] for m in self.mice)
        max_speed = max((m['highest_speed'] for m in self.mice), default=0)
        avg_speeds = [m['avg_speed'] for m in self.mice if m['avg_speed'] > 0]
        avg_speed = sum(avg_speeds) / len(avg_speeds) if avg_speeds else 0
        total_points = sum(len(m['path_points']) for m in self.mice)
        
        stats_text = f"Mice: {len(self.mice)}  •  Total points: {total_points}  •  Total dist: {total_dist:.1f} px  •  Avg speed: {avg_speed:.2f} px/s  •  Max: {max_speed:.2f} px/s"
        stats_lbl = tk.Label(bottom, text=stats_text, bg=self.colors['bg_medium'], fg=self.colors['text_primary'], wraplength=650)
        stats_lbl.pack(side=tk.TOP, padx=6, pady=(5,10))

        btn_frame = tk.Frame(bottom, bg=self.colors['bg_medium'])
        btn_frame.pack(side=tk.TOP)

        save_csv_btn = tk.Button(btn_frame, text="Save Paths (CSV)", command=self.save_path_csv, bg=self.colors['accent_primary'], fg='white', relief=tk.FLAT, padx=10, pady=6, cursor='hand2')
        save_csv_btn.pack(side=tk.LEFT, padx=6)

        save_img_btn = tk.Button(btn_frame, text="Save Image (PNG)", command=self.save_path_image, bg=self.colors['accent_secondary'], fg='white', relief=tk.FLAT, padx=10, pady=6, cursor='hand2')
        save_img_btn.pack(side=tk.LEFT, padx=6)

        close_btn = tk.Button(btn_frame, text="Close", command=win.destroy, bg='#666666', fg='white', relief=tk.FLAT, padx=10, pady=6, cursor='hand2')
        close_btn.pack(side=tk.LEFT, padx=6)

    def save_path_csv(self):
        """Save recorded path points for all mice to CSV"""
        if not self.mice or not any(m['path_points'] for m in self.mice):
            messagebox.showinfo("No Data", "No path points to save.")
            return

        import csv

        filename = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv')], title='Save paths as CSV')
        if not filename:
            return

        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['mouse_id', 'frame_index', 'x', 'y', 'total_distance', 'avg_speed', 'max_speed'])
                
                for mouse_data in self.mice:
                    for i, p in enumerate(mouse_data['path_points']):
                        writer.writerow([
                            mouse_data['id'],
                            i,
                            p[0],
                            p[1],
                            round(mouse_data['total_distance'], 2),
                            round(mouse_data['avg_speed'], 2),
                            round(mouse_data['highest_speed'], 2)
                        ])
            messagebox.showinfo("Saved", f"Paths saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save CSV: {e}")

    def save_path_image(self):
        """Save the last frame with all drawn paths as PNG"""
        if self.original_frame is None:
            messagebox.showinfo("No Frame", "No frame available to save.")
            return

        filename = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG files','*.png')], title='Save image as PNG')
        if not filename:
            return

        try:
            img = self.original_frame.copy()
            if self.mice:
                self.draw_all_paths(img)
            cv2.imwrite(filename, img)
            messagebox.showinfo("Saved", f"Image saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save image: {e}")
    
    def draw_all_paths(self, frame):
        """Draw tracked paths for all mice with their colors"""
        for mouse_data in self.mice:
            if not mouse_data['path_points']:
                continue
            
            color = mouse_data['color']
            path_points = list(mouse_data['path_points'])
            
            # Draw path lines if we have at least 2 points
            if len(path_points) >= 2:
                thickness = 3
                for i in range(1, len(path_points)):
                    cv2.line(frame, path_points[i-1], path_points[i], color, thickness)
            
            # Draw all points as small circles for better visibility
            for point in path_points:
                cv2.circle(frame, point, 2, color, -1)
            
            # Draw current position marker with label
            if path_points:
                last_point = path_points[-1]
                # Outer circle
                cv2.circle(frame, last_point, 8, color, 2)
                # Inner filled circle
                cv2.circle(frame, last_point, 4, color, -1)
                
                # Draw mouse label
                label = f"Mouse {mouse_data['id']}"
                label_pos = (last_point[0] + 12, last_point[1] - 12)
                cv2.putText(frame, label, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    def draw_aggregate_stats(self, frame):
        """Draw aggregate statistics for all mice on the frame."""
        try:
            h, w = frame.shape[:2]
            
            # Position for stats overlay (top-right below speed meter if present)
            x_start = w - 250
            y_start = 20
            
            # Semi-transparent background
            overlay = frame.copy()
            cv2.rectangle(overlay, (x_start - 10, y_start - 5), (w - 10, y_start + 30 + len(self.mice) * 20), (30, 30, 30), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            
            # Title
            cv2.putText(frame, f"Tracking {len([m for m in self.mice if m['tracker']])}/{self.num_mice} mice", 
                       (x_start, y_start + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Individual mouse stats (brief)
            y_offset = y_start + 35
            for mouse_data in self.mice:
                if mouse_data['tracker']:
                    color = mouse_data['color']
                    text = f"M{mouse_data['id']}: {mouse_data['current_speed']:.0f} px/s"
                    cv2.putText(frame, text, (x_start, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                    y_offset += 18
        except Exception:
            pass
    
    def update_aggregate_ui_stats(self):
        """Update UI with aggregate statistics across all mice"""
        try:
            # Count tracked mice
            tracked = len([m for m in self.mice if m['tracker']])
            self.mice_count_label.config(text=f"{tracked}/{self.num_mice}")
            
            # Total distance
            total_dist = sum(m['total_distance'] for m in self.mice)
            self.distance_label.config(text=f"{total_dist:.1f} px")
            
            # Average speed across all mice
            speeds = [m['avg_speed'] for m in self.mice if m['avg_speed'] > 0]
            avg_speed = sum(speeds) / len(speeds) if speeds else 0
            self.speed_label.config(text=f"{avg_speed:.2f} px/s")
            
            # Highest speed across all mice
            max_speed = max((m['highest_speed'] for m in self.mice), default=0)
            self.max_speed_label.config(text=f"{max_speed:.2f} px/s")
        except Exception:
            pass
    
    def update_num_mice(self, value, label):
        """Update number of mice to track"""
        int_value = int(float(value))
        self.num_mice = int_value
        label.config(text=str(int_value))
        
        # Reset mice data when changing count
        self.initialize_mice_data()
        self.update_selection_status()

    def initialize_mice_data(self):
        """Initialize or reset data structures for all mice"""
        self.mice = []
        self.current_mouse_index = 0
        
        for i in range(self.num_mice):
            mouse_data = {
                'id': i + 1,
                'tracker': None,
                'bbox': None,
                'path_points': deque(maxlen=self.max_points_var.get()),
                'total_distance': 0,
                'avg_speed': 0,
                'current_speed': 0.0,
                'highest_speed': 0.0,
                'prev_time': None,
                'start_time': None,
                'color': self.mouse_colors[i % len(self.mouse_colors)]
            }
            self.mice.append(mouse_data)
    
    def update_selection_status(self):
        """Update the selection status label"""
        if not self.mice:
            self.selection_status_label.config(text="Ready to configure")
            return
        
        selected = len([m for m in self.mice if m['tracker']])
        if selected == self.num_mice:
            self.selection_status_label.config(text=f"✓ All {self.num_mice} mice selected")
        else:
            self.selection_status_label.config(text=f"Selected: {selected}/{self.num_mice} mice")

    def draw_path(self, frame):
        """Legacy method - now redirects to draw_all_paths"""
        self.draw_all_paths(frame)

    
    def display_frame(self, frame):
        """Display frame on canvas"""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Resize to fit canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width > 1 and canvas_height > 1:
            h, w = frame_rgb.shape[:2]
            aspect = w / h
            
            if canvas_width / canvas_height > aspect:
                new_height = canvas_height
                new_width = int(canvas_height * aspect)
            else:
                new_width = canvas_width
                new_height = int(canvas_width / aspect)
            
            frame_resized = cv2.resize(frame_rgb, (new_width, new_height))
            img = Image.fromarray(frame_resized)
            imgtk = ImageTk.PhotoImage(image=img)
            
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width//2, canvas_height//2, 
                                    image=imgtk, anchor=tk.CENTER)
            self.canvas.image = imgtk
    
    def start_selection(self):
        """Enable ROI selection mode for current mouse"""
        if self.current_frame is None:
            messagebox.showwarning("Warning", "No video frame available")
            return
        
        # Check if we need to initialize mice data
        if not self.mice:
            self.initialize_mice_data()
        
        # Find next mouse that needs selection
        self.current_mouse_index = -1
        for i, mouse in enumerate(self.mice):
            if mouse['tracker'] is None:
                self.current_mouse_index = i
                break
        
        if self.current_mouse_index == -1:
            messagebox.showinfo("Complete", "All mice have been selected!")
            return
        
        self.is_selecting = True
        self.temp_bbox = None
        mouse_num = self.current_mouse_index + 1
        self.status_label.config(text=f"🎯 Draw box around Mouse {mouse_num}", 
                                fg=self.colors['accent_warning'])
        self.update_button_state(self.select_btn, tk.DISABLED)
    
    def on_mouse_down(self, event):
        """Mouse button pressed"""
        if self.is_selecting:
            self.selection_start = (event.x, event.y)
    
    def on_mouse_drag(self, event):
        """Mouse dragged"""
        if self.is_selecting and self.selection_start:
            self.selection_end = (event.x, event.y)
            # Calculate bbox in frame coordinates
            self.temp_bbox = self.canvas_to_frame_coords(self.selection_start, self.selection_end)
    
    def on_mouse_up(self, event):
        """Mouse button released"""
        if self.is_selecting and self.selection_start:
            self.selection_end = (event.x, event.y)
            bbox = self.canvas_to_frame_coords(self.selection_start, self.selection_end)
            
            if bbox and bbox[2] > 10 and bbox[3] > 10:
                self.initialize_tracker_for_mouse(self.current_mouse_index, bbox)
                self.is_selecting = False
                self.temp_bbox = None
                
                # Update status and check if more selections needed
                self.update_selection_status()
                selected = len([m for m in self.mice if m['tracker']])
                
                if selected < self.num_mice:
                    # More mice to select
                    self.select_btn.config(text=f"🎯 Select Mouse {selected + 1}")
                    self.status_label.config(text=f"✅ Mouse {self.current_mouse_index + 1} selected. Select next mouse.", 
                                            fg=self.colors['accent_success'])
                    self.update_button_state(self.select_btn, tk.NORMAL)
                else:
                    # All mice selected
                    self.status_label.config(text=f"✅ All {self.num_mice} mice selected!", 
                                            fg=self.colors['accent_success'])
                    self.update_button_state(self.track_btn, tk.NORMAL)
                    self.update_button_state(self.select_btn, tk.DISABLED)
            else:
                messagebox.showwarning("Invalid Selection", 
                                      "Selection too small. Please draw a larger box.")
                self.is_selecting = False
                self.update_button_state(self.select_btn, tk.NORMAL)
    
    def canvas_to_frame_coords(self, start, end):
        """Convert canvas coordinates to frame coordinates"""
        if self.original_frame is None:
            return None
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        frame_h, frame_w = self.original_frame.shape[:2]
        
        # Calculate the displayed frame dimensions
        aspect = frame_w / frame_h
        if canvas_width / canvas_height > aspect:
            display_height = canvas_height
            display_width = int(canvas_height * aspect)
        else:
            display_width = canvas_width
            display_height = int(canvas_width / aspect)
        
        # Calculate offset
        offset_x = (canvas_width - display_width) // 2
        offset_y = (canvas_height - display_height) // 2
        
        # Convert coordinates
        x1 = int((start[0] - offset_x) * frame_w / display_width)
        y1 = int((start[1] - offset_y) * frame_h / display_height)
        x2 = int((end[0] - offset_x) * frame_w / display_width)
        y2 = int((end[1] - offset_y) * frame_h / display_height)
        
        # Ensure positive dimensions
        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)
        
        # Clamp to frame boundaries
        x = max(0, min(x, frame_w))
        y = max(0, min(y, frame_h))
        w = min(w, frame_w - x)
        h = min(h, frame_h - y)
        
        return (x, y, w, h)
    
    def initialize_tracker_for_mouse(self, mouse_index, bbox):
        """Initialize tracker for a specific mouse"""
        if self.original_frame is None or bbox is None:
            return
        
        if mouse_index < 0 or mouse_index >= len(self.mice):
            return
        
        try:
            tracker = cv2.legacy.TrackerCSRT_create()
        except AttributeError:
            tracker = cv2.TrackerCSRT_create()
        
        tracker.init(self.original_frame, bbox)
        
        # Update mouse data
        mouse_data = self.mice[mouse_index]
        mouse_data['tracker'] = tracker
        mouse_data['bbox'] = bbox
        
        # Add initial point
        center_x = int(bbox[0] + bbox[2] / 2)
        center_y = int(bbox[1] + bbox[3] / 2)
        mouse_data['path_points'].append((center_x, center_y))
        mouse_data['prev_time'] = time.time()
        mouse_data['current_speed'] = 0.0
    
    def initialize_tracker(self):
        """Legacy method - redirects to multi-mouse version"""
        if self.current_mouse_index >= 0:
            self.initialize_tracker_for_mouse(self.current_mouse_index, self.bbox if hasattr(self, 'bbox') else None)
    
    def start_tracking(self):
        """Start tracking all selected mice"""
        # Check if any mice have been selected
        selected = len([m for m in self.mice if m['tracker']])
        if selected == 0:
            messagebox.showwarning("Warning", "Please select at least one mouse first")
            return
        
        self.is_tracking = True
        self.preview_paused = False
        
        # Update buttons
        self.update_button_state(self.track_btn, tk.DISABLED)
        self.update_button_state(self.stop_btn, tk.NORMAL)
        self.update_button_state(self.select_btn, tk.DISABLED)
        
        # Enable Stop Recording only for webcam
        if self.is_webcam:
            self.update_button_state(self.stop_recording_btn, tk.NORMAL)
        
        self.status_label.config(text=f"🔴 Tracking {selected} mice...", 
                                fg=self.colors['accent_success'])
    
    def stop_tracking(self):
        """Pause tracking all mice"""
        self.is_tracking = False
        self.preview_paused = True
        
        # Update buttons
        self.update_button_state(self.track_btn, tk.NORMAL)
        self.update_button_state(self.stop_btn, tk.DISABLED)
        
        # Check if we can continue selecting
        unselected = len([m for m in self.mice if m['tracker'] is None])
        if unselected > 0:
            self.update_button_state(self.select_btn, tk.NORMAL)
        
        self.status_label.config(text="⏸️ Tracking paused", 
                                fg=self.colors['accent_warning'])
    
    def stop_recording(self):
        """Stop recording and show save dialog (webcam only)"""
        if not self.is_webcam:
            return
        
        # Stop tracking
        self.is_tracking = False
        self.preview_paused = True
        
        # Update buttons
        self.update_button_state(self.track_btn, tk.DISABLED)
        self.update_button_state(self.stop_btn, tk.DISABLED)
        self.update_button_state(self.select_btn, tk.DISABLED)
        self.update_button_state(self.stop_recording_btn, tk.DISABLED)
        
        self.status_label.config(text="⚪ Recording stopped", 
                                fg=self.colors['text_secondary'])
        
        # Show save summary
        self.show_save_summary()
    
    def clear_path(self):
        """Clear all paths and reset statistics"""
        for mouse_data in self.mice:
            mouse_data['path_points'].clear()
            mouse_data['total_distance'] = 0
            mouse_data['avg_speed'] = 0
            mouse_data['current_speed'] = 0.0
            mouse_data['highest_speed'] = 0
            mouse_data['prev_time'] = None
            mouse_data['start_time'] = None
        
        self.update_aggregate_ui_stats()
    
    def update_max_points(self, value, label):
        """Update maximum path points for all mice"""
        int_value = int(float(value))
        label.config(text=str(int_value))
        
        # Update maxlen for all mice
        for mouse_data in self.mice:
            mouse_data['path_points'] = deque(mouse_data['path_points'], maxlen=int_value)
    
    def stop_video(self):
        """Stop video capture and reset"""
        self.stop_thread = True
        self.is_tracking = False
        self.preview_paused = True
        
        if self.tracking_thread and self.tracking_thread.is_alive():
            self.tracking_thread.join(timeout=1)
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # Reset all mice data
        self.mice.clear()
        self.current_mouse_index = 0
        self.current_frame = None
        self.original_frame = None
        self.is_webcam = False
        
        # Reset UI
        try:
            self.mice_count_label.config(text="0/0")
            self.distance_label.config(text="0.0 px")
            self.speed_label.config(text="0.0 px/s")
            self.max_speed_label.config(text="0.0 px/s")
        except Exception:
            pass
        
        # Reset buttons
        self.update_button_state(self.track_btn, tk.DISABLED)
        self.update_button_state(self.stop_btn, tk.DISABLED)
        self.update_button_state(self.select_btn, tk.DISABLED)
        self.update_button_state(self.stop_recording_btn, tk.DISABLED)
    
    def on_closing(self):
        """Handle window closing"""
        self.stop_video()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = RatTrackerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()