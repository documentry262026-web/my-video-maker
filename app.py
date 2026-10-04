import streamlit as st
import edge_tts
import os
import asyncio
import requests
import re  # Yeh kachra saaf karne ke liye naya tool add kiya hai
import google.generativeai as genai
from moviepy.editor import VideoFileClip, AudioFileClip, vfx

# 👇 1. Yahan Apni 'AIzaSy...' wali Gemini Key daalo 👇
API_KEYS = [
    "AQ.Ab8RN6LfAGekryAEuY_0KtnAkhUxW66dCH8U0Ah9Ik7ZMUARIA"  
]

# 👇 2. Pixabay API Key (Set hai) 👇
PIXABAY_API_KEY = "57871281-bac58345c5fba7b07f0655556"

def generate_script(topic, duration):
    target_words = int(duration) * 2
    prompt = f"Write a voiceover script about '{topic}'. Language: Hinglish. Length: {target_words} words. Only return the spoken script text, strictly NO emojis, NO markdown, NO asterisks."
    last_error = ""
    for key in API_KEYS:
        try:
            genai.configure(api_key=key)
            # STRICTLY GEMINI 3.6 FLASH
            model = genai.GenerativeModel('gemini-3.6-flash')
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            last_error = str(e)
            continue
    return f"Error: {last_error}"

async def create_audio(text, voice):
    output_file = "voiceover.mp3"
    # 🔥 YAHAN HUA HAI FIX 🔥 (Script se saare emojis/symbols hatana)
    clean_text = re.sub(r'[^\w\s.,?!।\'-]', '', text) 
    
    if not clean_text.strip():
        clean_text = "Script empty ho gayi thi."
        
    communicate = edge_tts.Communicate(clean_text, voice)
    await communicate.save(output_file)
    return output_file

def get_pixabay_videos(query):
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={query} aesthetic&per_page=3"
    try:
        response = requests.get(url)
        if response.status_code != 200: return []
        data = response.json()
        video_urls = []
        for hit in data.get("hits", []):
            videos = hit.get("videos", {})
            if "medium" in videos and "url" in videos["medium"]:
                video_urls.append(videos["medium"]["url"])
            elif "large" in videos and "url" in videos["large"]:
                video_urls.append(videos["large"]["url"])
        return video_urls
    except:
        return []

def download_video(url, filename):
    r = requests.get(url, stream=True)
    with open(filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk: f.write(chunk)
    return filename

def assemble_video(audio_path, video_urls, ratio):
    if not video_urls: return None
    vid_path = download_video(video_urls[0], "bg_video.mp4")
    audio = AudioFileClip(audio_path)
    video = VideoFileClip(vid_path).without_audio()
    target_size = (1080, 1920) if ratio == "9:16 (Shorts)" else (1920, 1080)
    video = video.resize(height=target_size[1])
    if video.w < target_size[0]: video = video.resize(width=target_size[0])
    video = video.crop(x_center=video.w/2, y_center=video.h/2, width=target_size[0], height=target_size[1])
    if video.duration < audio.duration: video = video.fx(vfx.loop, duration=audio.duration)
    else: video = video.subclip(0, audio.duration)
    final = video.set_audio(audio)
    output = "final_output.mp4"
    final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", logger=None)
    return output

st.set_page_config(page_title="My Video Maker", page_icon="🎬", layout="centered")
st.title("🎬 My Free Video Maker")

topic = st.text_input("1. Topic", placeholder="Aesthetic nature, Gym workout...")
ratio = st.radio("2. Ratio", ["9:16 (Shorts)", "16:9 (YouTube)"])
duration = st.slider("3. Duration (sec)", 10, 30, 15, 5)
voice_choice = st.radio("4. Voiceover", ["Male Hinglish", "Female Hinglish"])

if st.button("🚀 Generate Video", type="primary"):
    if not topic:
        st.warning("Pehle koi topic daalo!")
    else:
        with st.status("Video ban raha hai... (Please wait)", expanded=True) as status:
            st.write("1. Gemini AI Script likh raha hai... ✍️")
            script = generate_script(topic, duration)
            
            if "Error:" in script:
                status.update(label="Error", state="error")
                st.error(f"AI Script fail ho gayi. Asli wajah: {script}")
            else:
                st.write("2. Voiceover ban raha hai... 🎙️")
                voice_id = "hi-IN-MadhurNeural" if "Male" in voice_choice else "hi-IN-SwaraNeural"
                
                try:
                    audio_path = asyncio.run(create_audio(script, voice_id))
                    
                    st.write("3. Pixabay se Aesthetic Video fetch ho raha hai... 🎥")
                    video_urls = get_pixabay_videos(topic)
                    
                    if not video_urls:
                        status.update(label="Partial Success", state="complete")
                        st.warning("Video fetch fail ho gaya. Sirf Audio ready hai.")
                        st.audio(audio_path)
                    else:
                        st.write("4. Final Video edit ho raha hai (1-2 min lagenge)... 🎬")
                        final_video = assemble_video(audio_path, video_urls, ratio)
                        
                        status.update(label="🎉 Video Ready!", state="complete")
                        st.success("Bhai, tumhara video successfully generate ho gaya!")
                        st.text_area("Generated Script", script, height=150)
                        st.video(final_video)
                except Exception as e:
                    status.update(label="Voiceover Error", state="error")
                    st.error("Voiceover tool me dikkat aayi. Wapas Generate dabao.")
