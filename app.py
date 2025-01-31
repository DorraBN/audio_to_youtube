from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
from mutagen.mp3 import MP3
from mutagen.mp3 import HeaderNotFoundError
from PIL import Image
from moviepy.editor import VideoFileClip, AudioFileClip
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import time

app = Flask(__name__)

UPLOAD_FOLDER = 'static/videos'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Fichier client secrets
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Fonction pour obtenir un service authentifié avec l'API YouTube
def get_authenticated_service():
    credentials = None
    try:
        if os.path.exists("token.json"):
            credentials = Credentials.from_authorized_user_file("token.json", SCOPES)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                credentials = flow.run_local_server(port=0)

            with open("token.json", "w") as token_file:
                token_file.write(credentials.to_json())

        youtube = build("youtube", "v3", credentials=credentials)
        return youtube
    except Exception as e:
        print(f"Erreur d'authentification YouTube : {e}")
        return None

@app.route("/upload_youtube/<video_filename>", methods=["POST"])
def upload_video(video_filename):
    try:
        title = request.form.get("title", "Titre par défaut")
        description = request.form.get("description", "Description par défaut")
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)

        if not os.path.exists(video_path):
            return "Le fichier vidéo n'existe pas.", 400

        youtube = get_authenticated_service()
        if youtube is None:
            return "Erreur d'authentification YouTube. Veuillez vous reconnecter.", 500

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': ["tag1", "tag2"],
                'categoryId': '22'
            },
            'status': {
                'privacyStatus': 'private'
            }
        }

        media_body = MediaFileUpload(video_path, chunksize=256 * 1024, resumable=True)
        insert_request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media_body
        )

        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                print(f"Progression de l'upload : {int(status.progress() * 100)}%")

        if 'id' in response:
            return jsonify({"message": "Vidéo uploadée avec succès !", "video_id": response['id']})
        else:
            return "Une erreur est survenue lors de l'upload de la vidéo.", 500
    except Exception as e:
        print(f"Erreur lors de l'upload de la vidéo : {e}")
        return f"Erreur : {str(e)}", 500


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            video_name = request.form.get("video_name")
            audio = request.files["audio"]
            images = request.files.getlist("images")

            if not audio.filename.endswith('.mp3'):
                return "Le fichier doit être au format MP3", 400

            audio_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'audio')
            os.makedirs(audio_folder, exist_ok=True)

            audio_path = os.path.join(audio_folder, audio.filename)
            audio.save(audio_path)

            folder_path = os.path.join(app.config['UPLOAD_FOLDER'], 'images')
            os.makedirs(folder_path, exist_ok=True)

            image_paths = []
            for img in images:
                img_path = os.path.join(folder_path, img.filename)
                img.save(img_path)
                image_paths.append(img_path)

            video_filename = f"{video_name}.mp4"
            video_path_name = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)

            mp3_to_mp4 = MP3ToMP4(folder_path, audio_path, video_path_name, image_paths)
            mp3_to_mp4.combine_audio()

            return redirect(url_for('display_video', video_filename=video_filename))
        except ValueError as e:
            return str(e), 400
        except Exception as e:
            print(f"Erreur dans la création de la vidéo : {e}")
            return "Une erreur est survenue lors du traitement.", 500

    return render_template("app.html")


@app.route("/video/<video_filename>")
def display_video(video_filename):
    video_url = url_for('static', filename=f'videos/{video_filename}')
    return render_template("app.html", video_url=video_url, video_filename=video_filename)


# Classe pour transformer un fichier MP3 en vidéo MP4 avec des images
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
        selected_images = self.get_selected_images()
        gif_path = os.path.join(self.folder_path, "temp.gif")

        # Calculer la durée par image en ms et la limiter
        duration_per_image = self.duration * 1000 // len(selected_images)
        duration_per_image = min(duration_per_image, 65535)  # Limiter la durée à 65535ms

        selected_images[0].save(
            gif_path,
            save_all=True,
            append_images=selected_images[1:],
            duration=duration_per_image,
            loop=0
        )

    def combine_audio(self):
        video = VideoFileClip(os.path.join(self.folder_path, "temp.gif"))
        audio = AudioFileClip(self.audio_path)
        final_video = video.set_audio(audio)
        final_video.write_videofile(self.video_path_name, fps=30)

@app.route("/oauth2callback")
def oauth2callback():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    redirect_uri = f"{request.scheme}://{request.host}/oauth2callback"
    flow.redirect_uri = redirect_uri

    code = request.args.get('code')
    if not code:
        # Étape 1 : Générer l'URL OAuth
        auth_url, _ = flow.authorization_url(prompt='consent')
        return jsonify({"oauth_url": auth_url})  # Fournir l'URL OAuth

    try:
        # Étape 2 : Traiter l'authentification
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Enregistrer les credentials dans un fichier local
        with open("token.json", "w") as token_file:
            token_file.write(credentials.to_json())

        # Une fois authentifié, uploader la vidéo
        youtube = get_authenticated_service()

        # Recherche de la vidéo générée automatiquement dans le dossier UPLOAD_FOLDER
        video_folder = app.config['UPLOAD_FOLDER']
        video_files = [f for f in os.listdir(video_folder) if f.endswith(".mp4")]

        if not video_files:
            return "Aucune vidéo générée n'a été trouvée.", 400

        # On prend le dernier fichier généré
        video_filename = sorted(video_files, key=lambda x: os.path.getmtime(os.path.join(video_folder, x)))[-1]
        video_path = os.path.join(video_folder, video_filename)

        # Détails de la vidéo
        body = {
            'snippet': {
                'title': "Titre de la vidéo générée automatiquement",
                'description': "Description de la vidéo générée automatiquement",
                'tags': ["auto", "generated", "video"],
                'categoryId': '22'  # Catégorie de la vidéo
            },
            'status': {
                'privacyStatus': 'private'  # Modifier à 'public' si nécessaire
            }
        }

        media_body = MediaFileUpload(video_path, chunksize=256 * 1024, resumable=True)
        insert_request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media_body
        )

        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                print(f"Progression de l'upload : {int(status.progress() * 100)}%")

        # Vérifiez si l'upload est réussi
        if 'id' in response:
            video_id = response['id']
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            print(f"Vidéo uploadée avec succès : {youtube_url}")

            # Afficher un bloc avec l'URL et un bouton pour créer une nouvelle vidéo
            return render_template(
                "video_success.html",
                youtube_url=youtube_url
            )
        else:
            return "Une erreur est survenue lors de l'upload.", 500

    except Exception as e:
        print(f"Erreur lors de l'authentification ou de l'upload : {e}")
        return f"Une erreur est survenue : {str(e)}", 500



@app.route("/get_progress")
def get_progress():
  
    progress = int(time.time()) % 100  
    return jsonify({"progress": progress})




if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))