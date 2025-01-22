from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from pathlib import Path
import os
from mutagen.mp3 import MP3
from PIL import Image
from moviepy.editor import VideoFileClip, AudioFileClip
from googleapiclient.http import MediaFileUpload
import google.auth
from googleapiclient.discovery import build

app = Flask(__name__)

# Dossiers de téléchargement
UPLOAD_FOLDER = 'static/videos'  # Save videos in the 'static/videos' folder
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

class MP3ToMP4:
    def __init__(self, folder_path, audio_path, video_path_name, selected_image):
        self.folder_path = folder_path
        self.audio_path = audio_path
        self.video_path_name = video_path_name
        self.selected_image = selected_image  # New parameter for the selected image
        self.duration = self.get_length()  # Get the duration of the MP3
        self.create_video()

    def get_length(self):
        song = MP3(self.audio_path)
        return int(song.info.length)

    def get_selected_image(self):
        # Open the selected image and resize it
        image = Image.open(self.selected_image).resize((800, 800), Image.Resampling.LANCZOS)
        return image

    def create_video(self):
        if self.duration < 0 or self.duration > 65535:
            self.duration = 100  # Set a default value

        selected_image = self.get_selected_image()

        # Save the selected image as a GIF (even though it will only have one frame)
        selected_image.save(
            self.folder_path + "/temp.gif",
            save_all=True,
            duration=self.duration
        )

    def combine_audio(self):
        video = VideoFileClip(self.folder_path + "/temp.gif")
        audio = AudioFileClip(self.audio_path)
        final_video = video.set_audio(audio)
        final_video.write_videofile(self.video_path_name, fps=60)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        audio = request.files["audio"]
        audio_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'audio')
        os.makedirs(audio_folder, exist_ok=True)

        audio_path = os.path.join(audio_folder, audio.filename)
        audio.save(audio_path)

        images = request.files.getlist("images")
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], 'images')
        os.makedirs(folder_path, exist_ok=True)

        # Save all images to the folder
        for img in images:
            img_path = os.path.join(folder_path, img.filename)
            img.save(img_path)

        # Select only one image, for example, the first image
        selected_image_path = os.path.join(folder_path, images[0].filename)

        # Récupérer le nom de la vidéo depuis l'input
        video_name = request.form['video_name']
        video_filename = f"{video_name}.mp4"  # Créer le nom de la vidéo avec le nom saisi

        video_path_name = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)

        # Pass the selected image to the MP3ToMP4 class
        mp3_to_mp4 = MP3ToMP4(folder_path, audio_path, video_path_name, selected_image_path)
        mp3_to_mp4.combine_audio()

        return redirect(url_for('download_video', video_filename=video_filename))

    return render_template("app.html")

@app.route("/download/<video_filename>")
def download_video(video_filename):
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], video_filename)

def upload_video_to_youtube(file_path, title, description):
    credentials, project = google.auth.default(scopes=["https://www.googleapis.com/auth/youtube.upload"])
    youtube = build("youtube", "v3", credentials=credentials)

    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["audio", "mp3", "upload"]
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
    response = request.execute()

    return response

@app.route("/upload_to_youtube", methods=["POST"])
def upload_to_youtube():
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], "final_video.mp4")
    title = request.form['title']
    description = request.form['description']
    
    response = upload_video_to_youtube(video_path, title, description)
    return f"Video uploaded successfully: {response['id']}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
