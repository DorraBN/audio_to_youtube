from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
from mutagen.mp3 import MP3
from mutagen.mp3 import HeaderNotFoundError
from PIL import Image
from moviepy.editor import VideoFileClip, AudioFileClip

app = Flask(__name__)


UPLOAD_FOLDER = 'static/videos'  
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

class MP3ToMP4:
    def __init__(self, folder_path, audio_path, video_path_name, selected_images):
        self.folder_path = folder_path
        self.audio_path = audio_path
        self.video_path_name = video_path_name
        self.selected_images = selected_images 
        self.duration = self.get_length()  
        self.create_video()

    def get_length(self):
        try:
            song = MP3(self.audio_path)
            return int(song.info.length)
        except HeaderNotFoundError:
            raise ValueError("Le fichier MP3 est corrompu ou invalide.")
    
    def get_selected_images(self):
       
        images = []
        for img_path in self.selected_images:
            image = Image.open(img_path).resize((800, 800), Image.Resampling.LANCZOS)
            images.append(image)
        return images

    def create_video(self):
        if self.duration < 0 or self.duration > 65535:
            self.duration = 100  

        selected_images = self.get_selected_images()

        gif_path = self.folder_path + "/temp.gif"
        selected_images[0].save(
            gif_path,
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
        # Vérifier le fichier audio
        audio = request.files["audio"]
        if not audio.filename.endswith('.mp3'):
            return "Le fichier doit être au format MP3", 400

        audio_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'audio')
        os.makedirs(audio_folder, exist_ok=True)

        audio_path = os.path.join(audio_folder, audio.filename)
        audio.save(audio_path)

     
        images = request.files.getlist("images")
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], 'images')
        os.makedirs(folder_path, exist_ok=True)

        image_paths = []
        for img in images:
            img_path = os.path.join(folder_path, img.filename)
            img.save(img_path)
            image_paths.append(img_path)


        video_name = request.form['video_name']
        video_filename = f"{video_name}.mp4"  

        video_path_name = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)

        try:
           
            mp3_to_mp4 = MP3ToMP4(folder_path, audio_path, video_path_name, image_paths)
            mp3_to_mp4.combine_audio()
        except ValueError as e:
            return str(e), 400  

        return redirect(url_for('download_video', video_filename=video_filename))

    return render_template("app.html")

@app.route("/download/<video_filename>")
def download_video(video_filename):
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], video_filename)

if __name__ == "__main__":
    app.run(debug=True)
