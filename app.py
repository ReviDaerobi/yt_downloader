# app.py
from flask import Flask, render_template, request, send_file, jsonify
from yt_dlp import YoutubeDL
import io
import os

app = Flask(__name__)

def create_yt_dlp_opts(format_id=None, is_audio=False):
    """Create options for yt-dlp"""
    if is_audio:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        ydl_opts = {
            'format': format_id if format_id else 'bv*+ba/b',  # Get best video+audio format
        }

    # Common options
    ydl_opts.update({
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls'],  # Skip DASH and HLS formats
            },
        },
        # Uncomment and set these if needed
        # 'username': os.getenv('YT_USERNAME'),
        # 'password': os.getenv('YT_PASSWORD'),
    })

    return ydl_opts

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-formats', methods=['POST'])
def get_formats():
    url = request.form.get('url')
    if not url:
        return jsonify({'error': 'Please provide a valid YouTube URL'}), 400

    try:
        ydl_opts = create_yt_dlp_opts()
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return jsonify({'error': 'Could not fetch video information'}), 400

            formats = []
            # Filter for formats with both video and audio
            for f in info['formats']:
                # Skip formats without video or audio
                if not f.get('height') or f.get('vcodec') == 'none':
                    continue
                    
                height = f.get('height', 0)
                fps = f.get('fps', 0)
                filesize = f.get('filesize', 0)
                
                # Only include common resolutions
                if height in [144, 240, 360, 480, 720, 1080, 1440, 2160]:
                    formats.append({
                        'format_id': f['format_id'],
                        'ext': f['ext'],
                        'height': height,
                        'fps': fps,
                        'filesize': filesize,
                    })

            # Remove duplicates and sort by quality
            unique_formats = {}
            for f in formats:
                key = f['height']
                if key not in unique_formats or f['filesize'] > unique_formats[key]['filesize']:
                    unique_formats[key] = f

            # Convert to list and sort
            formats = list(unique_formats.values())
            formats.sort(key=lambda x: (x['height'], x['filesize']), reverse=True)

            # Format for display
            formatted_formats = []
            for f in formats:
                size_mb = f['filesize'] / 1024 / 1024 if f['filesize'] else 0
                label = f"{f['height']}p"
                if f['fps'] > 30:
                    label += f" {f['fps']}fps"
                if size_mb > 0:
                    label += f" (~{size_mb:.1f}MB)"

                formatted_formats.append({
                    'format_id': f['format_id'],
                    'label': label,
                    'height': f['height']
                })

            return jsonify({
                'formats': formatted_formats,
                'title': info['title']
            })

    except Exception as e:
        error_message = str(e)
        if 'Sign in to confirm your age' in error_message:
            return jsonify({'error': 'Age-restricted video. Cannot download.'}), 400
        elif 'Private video' in error_message:
            return jsonify({'error': 'This video is private.'}), 400
        elif 'This video is unavailable' in error_message:
            return jsonify({'error': 'Video is unavailable.'}), 400
        else:
            return jsonify({'error': f'An error occurred: {error_message}'}), 500

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    format_type = request.form.get('format')
    format_id = request.form.get('format_id')
    
    if not url:
        return 'Please provide a URL', 400
    
    try:
        buffer = io.BytesIO()
        ydl_opts = create_yt_dlp_opts(
            format_id=format_id if format_type == 'video' else None,
            is_audio=format_type == 'audio'
        )
        
        # Set output template to memory buffer
        ydl_opts['outtmpl'] = '-'
        
        with YoutubeDL(ydl_opts) as ydl:
            # Get info first for title
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')
            
            # Clean filename
            clean_title = "".join(c for c in title if c.isalnum() or c in (' ','-','_')).rstrip()
            filename = f"{clean_title}.{'mp3' if format_type == 'audio' else 'mp4'}"
            
            # Download to memory
            ydl.download([url])
            
            return send_file(
                buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='audio/mp3' if format_type == 'audio' else 'video/mp4'
            )
            
    except Exception as e:
        return f'Error: {str(e)}', 500

if __name__ == '__main__':
    app.run(debug=True)