import os
import io
from flask import Flask, request, render_template_string, send_file
import yt_dlp

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube M4A Ses İndirici</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .container { background-color: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); width: 100%; max-width: 500px; text-align: center; }
        h2 { color: #333; margin-bottom: 20px; }
        input[type="text"] { width: 100%; padding: 12px; margin-bottom: 20px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 14px; }
        button { background-color: #ff0000; color: white; border: none; padding: 12px 20px; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; width: 100%; transition: background 0.3s; }
        button:hover { background-color: #cc0000; }
        .footer { margin-top: 15px; font-size: 12px; color: #777; }
    </style>
</head>
<body>
    <div class="container">
        <h2>YouTube M4A İndirici</h2>
        <form method="POST" action="/download">
            <input type="text" name="url" placeholder="YouTube Video Linkini Yapıştırın" required autocomplete="off">
            <button type="submit">Ses Dosyasını İndir (.m4a)</button>
        </form>
        <div class="footer">Dosya arka planda işlenir ve doğrudan indirilir.</div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/download', methods=['POST'])
def download():
    video_url = request.form.get('url')
    if not video_url:
        return "Lütfen geçerli bir link girin.", 400

    # Render'ın Linux ortamında geçici dosyalar için güvenli dizin
    download_dir = '/tmp/ytdl_temp'
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]', 
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'restrictfilenames': True, 
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
        
        # Dosyayı belleğe al (Render'ın diski dolmasın diye)
        return_data = io.BytesIO()
        with open(filename, 'rb') as f:
            return_data.write(f.read())
        return_data.seek(0)
        
        # Sunucudaki orijinal dosyayı hemen sil
        os.remove(filename)
        
        download_name = os.path.basename(filename)

        # Bellekteki veriyi kullanıcıya gönder
        return send_file(
            return_data, 
            as_attachment=True, 
            download_name=download_name, 
            mimetype='audio/mp4'
        )
        
    except Exception as e:
        return f"İndirme sırasında bir hata oluştu: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
