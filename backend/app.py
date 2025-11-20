from flask import Flask, request, jsonify, send_file, Response
import os
import uuid
from werkzeug.utils import secure_filename
import sys
import traceback
import re
import time

backend_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(backend_dir, 'src')
sys.path.insert(0, backend_dir)
sys.path.insert(0, src_dir)

print(f"📁 Python paths: {sys.path}")

app = Flask(__name__)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'

# Create directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# CORS handling
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
    return response

@app.route('/api/process_video', methods=['OPTIONS', 'POST'])
def process_video():
    if request.method == 'OPTIONS':
        return '', 200
    
    print("🎬 Request received at /api/process_video")

    try:
        model_type = request.form.get('model_type')
        video_file = request.files.get('video')

        if not video_file or not video_file.filename:
            return jsonify({'success': False, 'message': 'No video file provided'}), 400

        # Validate file type
        if not video_file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            return jsonify({'success': False, 'message': 'Invalid file type. Please upload a video file.'}), 400

        # Generate unique names
        file_id = str(uuid.uuid4())
        input_filename = f"{file_id}_{secure_filename(video_file.filename)}"
        input_path = os.path.join(UPLOAD_FOLDER, input_filename)
        output_filename = f"processed_{file_id}.mp4"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        # Save uploaded video
        video_file.save(input_path)
        print(f"✅ Saved input video: {input_path} (Size: {os.path.getsize(input_path)} bytes)")

        # Process based on model type
        if model_type == 'object_detection':
            print(f"🔄 Processing video with object detection: {input_path} -> {output_path}")
            
            try:
                # Import object detection module
                from object_detection import process_video as process_object_detection
                process_object_detection(input_path, output_path)
                print(f"✅ Object detection completed: {output_path}")
                
            except Exception as e:
                print(f"❌ Object detection error: {e}")
                traceback.print_exc()
                # Clean up input file
                if os.path.exists(input_path):
                    os.remove(input_path)
                return jsonify({'success': False, 'message': f'Object detection failed: {str(e)}'}), 500

        elif model_type == 'three_seater':
            print(f"🔄 Processing video with three seater detection: {input_path} -> {output_path}")
            
            try:
                # Import three seater detection module
                from three_seater_detection import process_video as process_three_seater
                
                # Process video without real-time callbacks (simpler approach)
                output_path, alert_history = process_three_seater(input_path, output_path)
                
                print(f"✅ Three seater detection completed: {output_path}")
                print(f"📊 Total alerts generated: {len(alert_history)}")
                
                # Return success response with alert information
                return jsonify({
                    'success': True, 
                    'message': 'Three seater detection completed successfully',
                    'output_path': output_path,
                    'total_alerts': len(alert_history),
                    'alerts': alert_history  # All alerts are returned at once
                })
                
            except Exception as e:
                print(f"❌ Three seater detection error: {e}")
                traceback.print_exc()
                if os.path.exists(input_path):
                    os.remove(input_path)
                return jsonify({'success': False, 'message': f'Three seater detection failed: {str(e)}'}), 500

        
        elif model_type == 'speed_estimation':
            print(f"🔄 Processing video with speed estimation: {input_path} -> {output_path}")
            
            try:
                # Import speed estimation module
                from speed_estimation import process_video as process_speed_estimation
                
                # Process video and get alerts - FIX THIS LINE:
                output_path, alert_history = process_speed_estimation(input_path, output_path)
                
                print(f"✅ Speed estimation completed: {output_path}")
                print(f"📊 Total alerts generated: {len(alert_history)}")
                
                # Extract just the filename for output_file
                output_filename = os.path.basename(output_path)
                
                # Return success response with alert information
                return jsonify({
                    'success': True, 
                    'message': 'Speed estimation completed successfully',
                    'output_path': output_path,
                    'output_file': output_filename,  # ADD THIS LINE
                    'total_alerts': len(alert_history),
                    'alerts': alert_history
                })
                
            except Exception as e:
                print(f"❌ Speed estimation error: {e}")
                traceback.print_exc()
                if os.path.exists(input_path):
                    os.remove(input_path)
                return jsonify({'success': False, 'message': f'Speed estimation failed: {str(e)}'}), 500
                    
        elif model_type == 'number_plate_detection':
            print(f"🔄 Processing video with NUMBER PLATE DETECTION: {input_path} -> {output_path}")
            
            try:
                from number_plate import process_video as process_number_plate
                print("✅ Imported NUMBER PLATE DETECTION module")
                process_number_plate(input_path, output_path)
                print(f"✅ NUMBER PLATE DETECTION completed: {output_path}")
                
            except Exception as e:
                print(f"❌ NUMBER PLATE DETECTION error: {e}")
                import traceback
                traceback.print_exc()
                if os.path.exists(input_path):
                    os.remove(input_path)
                return jsonify({'success': False, 'message': f'Number plate detection failed: {str(e)}'}), 500

        elif model_type == 'helmet_detection':
            print(f"🔄 Processing video with HELMET DETECTION: {input_path} -> {output_path}")
            
            try:
                from helmet_detection import process_video as process_helmet_detection
                print("✅ Imported HELMET DETECTION module")
                process_helmet_detection(input_path, output_path)
                print(f"✅ HELMET DETECTION completed: {output_path}")
                
            except Exception as e:
                print(f"❌ HELMET DETECTION error: {e}")
                import traceback
                traceback.print_exc()
                if os.path.exists(input_path):
                    os.remove(input_path)
                return jsonify({'success': False, 'message': f'Helmet detection failed: {str(e)}'}), 500

             
        else:
            # Clean up input file for unknown model type
            if os.path.exists(input_path):
                os.remove(input_path)
            return jsonify({'success': False, 'message': f'Unknown model type: {model_type}'}), 400

        # Clean up input file after successful processing
        if os.path.exists(input_path):
            os.remove(input_path)
            print(f"🧹 Cleaned up input file: {input_path}")

        return jsonify({
            "success": True,
            "output_file": output_filename,
            "file_id": output_filename,
            "message": "Video processed successfully",
        })

    except Exception as e:
        print(f"💥 ERROR in process_video: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks

@app.route('/api/stream/<filename>')
def stream_video(filename):
    try:
        # Secure filename check
        if '..' in filename or filename.startswith('/'):
            return jsonify({"error": "Invalid filename"}), 400
            
        video_path = os.path.join(OUTPUT_FOLDER, filename)
        print(f"🎥 Streaming video: {video_path}")

        if not os.path.exists(video_path):
            print(f"❌ File not found: {video_path}")
            return jsonify({"error": "File not found"}), 404

        return send_file_partial(video_path)

    except Exception as e:
        print(f"❌ Streaming error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def send_file_partial(path):
    """Handle HTTP Range requests for video streaming"""
    try:
        size = os.path.getsize(path)
        range_header = request.headers.get('Range', None)
        
        if not range_header:
            return send_file(path, mimetype='video/mp4')

        # Parse range header
        byte_range = range_header.replace('bytes=', '').split('-')
        start = int(byte_range[0]) if byte_range[0] else 0
        end = int(byte_range[1]) if byte_range[1] and byte_range[1] else size - 1

        # Validate range
        if start >= size or end >= size or start > end:
            return Response(status=416, headers={
                'Content-Range': f'bytes */{size}'
            })

        length = end - start + 1

        def generate():
            with open(path, 'rb') as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk_size = min(CHUNK_SIZE, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        response = Response(generate(), status=206, mimetype='video/mp4')
        response.headers.add('Content-Range', f'bytes {start}-{end}/{size}')
        response.headers.add('Accept-Ranges', 'bytes')
        response.headers.add('Content-Length', str(length))
        return response

    except Exception as e:
        print(f"❌ Error in send_file_partial: {str(e)}")
        return send_file(path, mimetype='video/mp4')

@app.route('/api/download/<filename>')
def download_video(filename):
    try:
        # Secure filename check
        if '..' in filename or filename.startswith('/'):
            return jsonify({"error": "Invalid filename"}), 400
            
        video_path = os.path.join(OUTPUT_FOLDER, filename)
        print(f"📥 Download requested: {video_path}")
        
        if not os.path.exists(video_path):
            print(f"❌ File not found: {video_path}")
            return jsonify({"error": "File not found"}), 404
            
        return send_file(video_path, as_attachment=True, download_name=filename)
        
    except Exception as e:
        print(f"❌ Download error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/cleanup', methods=['POST'])
def cleanup_files():
    """Clean up old files to prevent disk space issues"""
    try:
        cutoff_time = time.time() - (24 * 60 * 60)  # 24 hours ago
        
        deleted_files = 0
        for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if os.path.isfile(file_path) and os.path.getctime(file_path) < cutoff_time:
                    os.remove(file_path)
                    deleted_files += 1
                    
        return jsonify({'success': True, 'message': f'Cleaned up {deleted_files} old files'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy', 
        'message': 'Backend is running!',
        'upload_folder_size': len(os.listdir(UPLOAD_FOLDER)),
        'output_folder_size': len(os.listdir(OUTPUT_FOLDER))
    })

if __name__ == '__main__':
    print("🚀 Starting Flask server...")
    app.run(debug=False, host='0.0.0.0', port=5000)