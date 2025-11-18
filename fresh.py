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
        self.tracker = None
        self.bbox = None
        self.path_points = deque(maxlen=1000)
        self.is_tracking = False
        self.is_selecting = False
        self.video_source = None
        self.current_frame = None
        self.original_frame = None
        self.selection_start = None
        self.selection_end = None
        self.temp_bbox = None
        
        # Thread control
        self.stop_thread = False
        self.tracking_thread = None
        self.preview_paused = True
        
        # Statistics
        self.total_distance = 0
        self.avg_speed = 0
        self.frame_count = 0
        self.start_time = None
        
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
        top_bar = tk.Frame(main_container, bg=self.colors['bg_medium'], height=65)
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
        
        # Distance stat
        dist_frame = self.create_stat_card(stats_frame, "Distance", "0.0 px", 
                                          self.colors['accent_success'])
        dist_frame.pack(side=tk.LEFT, padx=4)
        self.distance_label = dist_frame.value_label
        
        # Speed stat
        speed_frame = self.create_stat_card(stats_frame, "Avg Speed", "0.0 px/s", 
                                           self.colors['accent_warning'])
        speed_frame.pack(side=tk.LEFT, padx=4)
        self.speed_label = speed_frame.value_label
        
        # Points stat
        points_frame = self.create_stat_card(stats_frame, "Path Points", "0", 
                                            self.colors['accent_primary'])
        points_frame.pack(side=tk.LEFT, padx=4)
        self.points_stat_label = points_frame.value_label
        
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
        
        self.video_btn = self.create_gradient_button(
            source_frame.content, "📁 Load Video File", self.load_video,
            self.colors['accent_secondary'], self.colors['accent_secondary']
        )
        self.video_btn.pack(fill=tk.X, pady=2)
        
        # Tracking Controls Section
        control_frame = self.create_section_frame(inner_left, "🎯 Tracking Controls")
        control_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.select_btn = self.create_gradient_button(
            control_frame.content, "🎯 Select Target", self.start_selection,
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
            btn_row, "⏹️ Stop", self.stop_tracking,
            self.colors['accent_danger'], self.colors['accent_danger'], tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))
        
        self.clear_btn = self.create_gradient_button(
            control_frame.content, "🗑️ Clear Path", self.clear_path,
            '#ff8800', '#ff8800'
        )
        self.clear_btn.pack(fill=tk.X, pady=3)
        
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
                                     wraplength=280, justify=tk.LEFT, anchor=tk.W)
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
        label_widget.pack(padx=15, pady=(8, 2))
        
        value_label = tk.Label(card, text=value, 
                              font=('Segoe UI', 12, 'bold'), 
                              bg=self.colors['bg_light'], 
                              fg=color)
        value_label.pack(padx=15, pady=(2, 8))
        
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

    
    def use_webcam(self):
        """Initialize webcam"""
        self.stop_video()
        self.cap = cv2.VideoCapture(0)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.video_source = 0
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
        """Main video display loop with enhanced statistics"""
        prev_point = None
        
        while not self.stop_thread and self.cap is not None and self.cap.isOpened():
            should_fetch_frame = not self.preview_paused or self.original_frame is None
            if should_fetch_frame:
                ret, frame = self.cap.read()
                if not ret:
                    # If it's a file, treat EOF as end of session (do not loop)
                    if isinstance(self.video_source, str):
                        # schedule UI handling on main thread and exit loop
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
            
            # Track if tracking is active
            if self.is_tracking and self.tracker is not None:
                if self.start_time is None:
                    self.start_time = time.time()
                
                success, bbox = self.tracker.update(self.original_frame)
                if success:
                    self.bbox = bbox
                    center_x = int(bbox[0] + bbox[2] / 2)
                    center_y = int(bbox[1] + bbox[3] / 2)
                    current_point = (center_x, center_y)
                    
                    # Calculate distance
                    if prev_point:
                        distance = math.sqrt((current_point[0] - prev_point[0])**2 + 
                                           (current_point[1] - prev_point[1])**2)
                        self.total_distance += distance
                    
                    prev_point = current_point
                    self.path_points.append(current_point)
                    
                    # Calculate speed
                    if self.start_time and len(self.path_points) > 1:
                        elapsed_time = time.time() - self.start_time
                        if elapsed_time > 0:
                            self.avg_speed = self.total_distance / elapsed_time
                    
                    # Draw enhanced bounding box with glow effect
                    p1 = (int(bbox[0]), int(bbox[1]))
                    p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                    
                    # Outer glow
                    cv2.rectangle(self.current_frame, 
                                (p1[0]-2, p1[1]-2), (p2[0]+2, p2[1]+2), 
                                (0, 255, 255), 1)
                    # Main box
                    cv2.rectangle(self.current_frame, p1, p2, (0, 255, 0), 3)
                    
                    # Label background
                    label = "Tracking Active"
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                    cv2.rectangle(self.current_frame, 
                                (p1[0], p1[1] - label_size[1] - 15), 
                                (p1[0] + label_size[0] + 10, p1[1]), 
                                (0, 255, 0), -1)
                    cv2.putText(self.current_frame, label, 
                              (p1[0] + 5, p1[1] - 8), 
                              cv2.FONT_HERSHEY_SIMPLEX, 
                              0.7, (0, 0, 0), 2)
                else:
                    # Tracking lost indicator
                    cv2.putText(self.current_frame, "⚠ Tracking Lost!", 
                              (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 
                              1.0, (0, 0, 255), 3)
            
            # Draw enhanced path
            self.draw_path(self.current_frame)
            
            # Draw temporary selection box
            if self.is_selecting and self.temp_bbox:
                x, y, w, h = self.temp_bbox
                # Animated dashed box effect
                cv2.rectangle(self.current_frame, (x, y), (x+w, y+h), (255, 255, 0), 3)
                cv2.rectangle(self.current_frame, (x-2, y-2), (x+w+2, y+h+2), (0, 255, 255), 1)
                
                # Label
                label_text = "Release to confirm selection"
                label_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(self.current_frame, 
                            (x, y - label_size[1] - 15), 
                            (x + label_size[0] + 10, y), 
                            (255, 255, 0), -1)
                cv2.putText(self.current_frame, label_text, 
                          (x + 5, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 
                          0.6, (0, 0, 0), 2)
            
            # Update display
            self.display_frame(self.current_frame)
            
            # Update UI statistics
            self.points_label.config(text=f"Path: {len(self.path_points)} points")
            self.points_stat_label.config(text=str(len(self.path_points)))
            self.distance_label.config(text=f"{self.total_distance:.1f} px")
            self.speed_label.config(text=f"{self.avg_speed:.2f} px/s")
            
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
        """Display a small window summarizing the recorded path and allow saving"""
        if not self.original_frame is None:
            preview_img = self.original_frame.copy()
        else:
            preview_img = None

        # Draw the recorded path onto a copy for preview
        if preview_img is not None and len(self.path_points) > 0:
            self.draw_path(preview_img)

        win = tk.Toplevel(self.root)
        win.title("Recording Complete — Save Path")
        win.configure(bg=self.colors['bg_medium'])
        win.geometry("700x520")

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

        stats_lbl = tk.Label(bottom, text=f"Path points: {len(self.path_points)}  •  Distance: {self.total_distance:.1f} px  •  Avg speed: {self.avg_speed:.2f} px/s", bg=self.colors['bg_medium'], fg=self.colors['text_primary'])
        stats_lbl.pack(side=tk.LEFT, padx=6)

        btn_frame = tk.Frame(bottom, bg=self.colors['bg_medium'])
        btn_frame.pack(side=tk.RIGHT)

        save_csv_btn = tk.Button(btn_frame, text="Save Path (CSV)", command=self.save_path_csv, bg=self.colors['accent_primary'], fg='white', relief=tk.FLAT, padx=10, pady=6, cursor='hand2')
        save_csv_btn.pack(side=tk.LEFT, padx=6)

        save_img_btn = tk.Button(btn_frame, text="Save Image (PNG)", command=self.save_path_image, bg=self.colors['accent_secondary'], fg='white', relief=tk.FLAT, padx=10, pady=6, cursor='hand2')
        save_img_btn.pack(side=tk.LEFT, padx=6)

        close_btn = tk.Button(btn_frame, text="Close", command=win.destroy, bg='#666666', fg='white', relief=tk.FLAT, padx=10, pady=6, cursor='hand2')
        close_btn.pack(side=tk.LEFT, padx=6)

    def save_path_csv(self):
        """Save recorded path points to CSV"""
        if not self.path_points:
            messagebox.showinfo("No Data", "No path points to save.")
            return

        from datetime import datetime
        import csv

        filename = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv')], title='Save path as CSV')
        if not filename:
            return

        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['index','x','y'])
                for i, p in enumerate(self.path_points):
                    writer.writerow([i, p[0], p[1]])
            messagebox.showinfo("Saved", f"Path saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save CSV: {e}")

    def save_path_image(self):
        """Save the last frame with drawn path as PNG"""
        if self.original_frame is None:
            messagebox.showinfo("No Frame", "No frame available to save.")
            return

        filename = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG files','*.png')], title='Save image as PNG')
        if not filename:
            return

        try:
            img = self.original_frame.copy()
            if self.path_points:
                self.draw_path(img)
            cv2.imwrite(filename, img)
            messagebox.showinfo("Saved", f"Image saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save image: {e}")
    
    def draw_path(self, frame):
        """Draw the tracked path with solid color"""
        if len(self.path_points) < 2:
            return
        
        # Draw path with solid cyan color
        path_color = (255, 255, 0)  # Cyan in BGR
        thickness = 3
        
        for i in range(1, len(self.path_points)):
            cv2.line(frame, self.path_points[i-1], self.path_points[i], path_color, thickness)
        
        # Draw current position marker
        if self.path_points:
            # Outer circle
            cv2.circle(frame, self.path_points[-1], 8, (0, 255, 255), 2)
            # Inner filled circle
            cv2.circle(frame, self.path_points[-1], 4, (0, 255, 0), -1)

    
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
        """Enable ROI selection mode"""
        if self.current_frame is None:
            messagebox.showwarning("Warning", "No video frame available")
            return
        
        self.is_selecting = True
        self.temp_bbox = None
        self.status_label.config(text="🎯 Draw a box around the rat to track", 
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
                self.bbox = bbox
                self.initialize_tracker()
                self.is_selecting = False
                self.temp_bbox = None
                self.status_label.config(text="✅ Target locked! Ready to track", 
                                        fg=self.colors['accent_success'])
                self.update_button_state(self.track_btn, tk.NORMAL)
                self.update_button_state(self.select_btn, tk.NORMAL)
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
    
    def initialize_tracker(self):
        """Initialize the tracker"""
        if self.original_frame is None or self.bbox is None:
            return
        
        try:
            self.tracker = cv2.legacy.TrackerCSRT_create()
        except AttributeError:
            self.tracker = cv2.TrackerCSRT_create()
        
        self.tracker.init(self.original_frame, self.bbox)
        
        # Add initial point
        center_x = int(self.bbox[0] + self.bbox[2] / 2)
        center_y = int(self.bbox[1] + self.bbox[3] / 2)
        self.path_points.append((center_x, center_y))
    
    def start_tracking(self):
        """Start tracking"""
        if self.tracker is None:
            messagebox.showwarning("Warning", "Please select the rat first")
            return
        
        self.is_tracking = True
        self.preview_paused = False
        if self.start_time is None:
            self.start_time = time.time()
        
        # Update buttons
        self.update_button_state(self.track_btn, tk.DISABLED)
        self.update_button_state(self.stop_btn, tk.NORMAL)
        self.update_button_state(self.select_btn, tk.DISABLED)
        
        self.status_label.config(text="🔴 Tracking in progress...", 
                                fg=self.colors['accent_success'])
    
    def stop_tracking(self):
        """Stop tracking"""
        self.is_tracking = False
        self.preview_paused = True
        
        # Update buttons
        self.update_button_state(self.track_btn, tk.NORMAL)
        self.update_button_state(self.stop_btn, tk.DISABLED)
        self.update_button_state(self.select_btn, tk.NORMAL)
        
        self.status_label.config(text="⏸️ Tracking stopped", 
                                fg=self.colors['accent_warning'])
    
    def clear_path(self):
        """Clear the path points and reset statistics"""
        self.path_points.clear()
        self.total_distance = 0
        self.avg_speed = 0
        self.start_time = None
        self.points_label.config(text="Path: 0 points")
        self.points_stat_label.config(text="0")
        self.distance_label.config(text="0.0 px")
        self.speed_label.config(text="0.0 px/s")
    
    def update_max_points(self, value, label):
        """Update maximum path points"""
        int_value = int(float(value))
        self.path_points = deque(self.path_points, maxlen=int_value)
        label.config(text=str(int_value))
    
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
        
        self.tracker = None
        self.bbox = None
        self.path_points.clear()
        self.current_frame = None
        self.original_frame = None
        self.total_distance = 0
        self.avg_speed = 0
        self.start_time = None
        
        # Reset buttons
        self.update_button_state(self.track_btn, tk.DISABLED)
        self.update_button_state(self.stop_btn, tk.DISABLED)
        self.update_button_state(self.select_btn, tk.DISABLED)
    
    def on_closing(self):
        """Handle window closing"""
        self.stop_video()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = RatTrackerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()