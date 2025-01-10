# app.py
from flask import Flask, render_template, request, send_file, jsonify, Response
from yt_dlp import YoutubeDL
import io
import os

app = Flask(__name__)

def get_buffer_stream(url, format_id=None, is_audio=False):
    """Download to memory buffer instead of file"""
    buffer = io.BytesIO()
    
    if is_audio:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': '-',
        }
    else:
        ydl_opts = {
            'format': format_id if format_id else 'best',
            'outtmpl': '-',
        }

    # Add common options
    ydl_opts.update({
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False
    })

    with YoutubeDL(ydl_opts) as ydl:
        # Get video info first
        info = ydl.extract_info(url, download=False)
        title = info.get('title', 'video')
        
        # Download to buffer
        info = ydl.extract_info(url)
        video_data = ydl.download([url])
        
    buffer.seek(0)
    return buffer, title

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-formats', methods=['POST'])
def get_formats():
    url = request.form.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'format': 'best'
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            
            # Get all formats with both video and audio
            for f in info['formats']:
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    height = f.get('height', 0)
                    fps = f.get('fps', 0)
                    
                    # Calculate approximate filesize if not provided
                    filesize = f.get('filesize', 0)
                    if not filesize and f.get('tbr'):
                        # Estimate based on bitrate
                        duration = info.get('duration', 0)
                        filesize = (f['tbr'] * 1024 * duration) / 8
                    
                    formats.append({
                        'format_id': f['format_id'],
                        'ext': f['ext'],
                        'height': height,
                        'fps': fps,
                        'filesize': filesize,
                        'format_note': f.get('format_note', ''),
                        'tbr': f.get('tbr', 0)  # Total bitrate
                    })
            
            # Sort by height then bitrate
            formats.sort(key=lambda x: (x['height'], x['tbr']), reverse=True)
            
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
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    format_type = request.form.get('format')
    format_id = request.form.get('format_id')
    
    if not url:
        return 'Please provide a URL', 400
    
    try:
        buffer, title = get_buffer_stream(
            url, 
            format_id=format_id if format_type == 'video' else None,
            is_audio=format_type == 'audio'
        )
        
        # Clean filename
        clean_title = "".join(c for c in title if c.isalnum() or c in (' ','-','_')).rstrip()
        filename = f"{clean_title}.{'mp3' if format_type == 'audio' else 'mp4'}"
        
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