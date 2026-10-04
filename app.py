import streamlit as st
import os
import requests
import re
import urllib.parse
import google.generativeai as genai
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

# ================= K E Y S =================
# 👇 1. Yahan Apni wahi working 'AIzaSy...' wali Gemini Key daalo 👇
API_KEYS = [
    "AQ.Ab8RN6JD7UflDlIwhNt6sZVcwhz1gLg4u5j9OWrOsLN8Pf8OnA"  
]

# 👇 2. Tumhari Pixabay Key Set Hai 👇
PIXABAY_API_KEY = "57871281-bac58345c5fba7b07f0655556"

# ================= 1. GEMINI SCRIPT =================
def generate_script(topic, duration):
    target_words = int(duration) * 2
    prompt = f"Write a voiceover script about '{topic}'. Language: Hinglish. Length: {target_words} words. Only return plain spoken text, strictly NO emojis, NO hashtags, NO asterisks."
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

# ================= 2. BULLETPROOF GOOGLE VOICEOVER =================
def create_audio(text, voice_choice, output_file="voiceover.mp3"):
    # Saare emojis aur symbols saaf karna
    clean = re.sub(r'[^\w\s.,?!।\'-]', ' ', text).strip()
    words = clean.split()
    if not words:
        words = ["Aesthetic", "video", "shuru", "ho", "raha", "hai"]
    
    # Language: Male ke liye Indian English/Hinglish, Female ke liye Hindi
    lang = "en-IN" if "Male" in voice_choice else "hi"
    
    # Text ko chote-chote chunks me baantna taaki kabhi fail na ho
    chunks = []
    curr = ""
    for w in words:
        if len(curr) + len(w) + 1 <= 100:
            curr += (" " if curr else "") + w
        else:
            if curr:
                chunks.append(curr)
            curr = w
    if curr:
        chunks.append(curr)
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    audio_data = bytearray()
    for chunk in chunks:
        q = urllib.parse.quote(chunk)
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={q}&tl={lang}&client=tw-ob"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200 and len(res.content) > 50:
                audio_data.extend(res.content)
            else:
                # Fallback to standard Hindi
                fallback_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={q}&tl=hi&client=tw-ob"
                fb_res = requests.get(fallback_url, headers=headers, timeout=10)
                if fb_res.status_code == 200:
                    audio_data.extend(fb_res.content)
        except Exception:
            continue
            
    if len(audio_data) > 200:
        with open(output_file, "wb") as f:
            f.write(audio_data)
        return output_file
        
    # Agar internet ka koi issue bhi ho, backup audio
    with open(output_file, "wb") as f:
        f.write(b'\xff\xfb\x90\x44' * 500)
    return output_file

# ================= 3. PIXABAY VIDEO FETCH =================
def get_pixabay_videos(query):
    # Agar user ke topic me video na mile toh automatic aesthetic fallback
    search_queries = [query.strip(), "nature aesthetic", "cinematic landscape", "night city"]
    for q in search_queries:
        try:
            params = {
                "key": PIXABAY_API_KEY,
                "q": q,
                "per_page": 5,
                "safesearch": "true"
            }
            res = requests.get("https://pixabay.com/api/videos/", params=params, timeout=10)
            if res.status_code == 200:
                hits = res.json().get("hits", [])
                urls = []
                for hit in hits:
                    vids = hit.get("videos", {})
                    for qual in ["medium", "large", "small"]:
                        if qual in vids and vids[qual].get("url"):
                            urls.append(vids[qual]["url"])
                            break
                if urls:
                    return urls
        except Exception:
            continue
    return []

def download_video(url, filename="bg_video.mp4"):
    res = requests.get(url, stream=True, timeout=30)
    with open(filename, "wb") as f:
        for chunk in res.iter_content(chunk_size=1024*1024):
            if chunk:
                f.write(chunk)
    return filename

# ================= 4. VIDEO EDITOR =================
def assemble_video(audio_path, video_urls, ratio):
    if not video_urls:
        return None
    vid_path = download_video(video_urls[0], "bg_video.mp4")
    audio = AudioFileClip(audio_path)
    video = VideoFileClip(vid_path).without_audio()
    
    target_size = (1080, 1920) if ratio == "9:16 (Shorts)" else (1920, 1080)
    video = video.resize(height=target_size[1])
    if video.w < target_size[0]:
        video = video.resize(width=target_size[0])
    video = video.crop(x_center=video.w/2, y_center=video.h/2, width=target_size[0], height=target_size[1])
    
    # Video duration ko audio duration ke barabar loop karna
    if video.duration < audio.duration:
        repeats = int(audio.duration // video.duration) + 1
        video = concatenate_videoclips([video] * repeats)
    video = video.subclip(0, audio.duration)
    
    final = video.set_audio(audio)
    output = "final_output.mp4"
    final.write_videofile(
        output,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp-audio.m4a",
        remove_temp=True,
        logger=None
    )
    return output

# ================= UI =================
st.set_page_config(page_title="My Video Maker", page_icon="🎬", layout="centered")
st.title("🎬 My Free Video Maker")

topic = st.text_input("1. Topic", placeholder="Aesthetic nature, Gym motivation, Rainy vibes...")
ratio = st.radio("2. Ratio", ["9:16 (Shorts)", "16:9 (YouTube)"])
duration = st.slider("3. Duration (sec)", 10, 30, 15, 5)
voice_choice = st.radio("4. Voiceover", ["Male Hinglish", "Female Hinglish"])

if st.button("🚀 Generate Video", type="primary"):
    if not topic:
        st.warning("Pehle koi topic daalo!")
    else:
        with st.status("Video ban raha hai... (Thoda sabr rakhein)", expanded=True) as status:
            st.write("1. Gemini AI Script likh raha hai... ✍️")
            script = generate_script(topic, duration)
            
            if "Error:" in script:
                status.update(label="Script Error", state="error")
                st.error(f"AI Script fail ho gayi: {script}")
            else:
                st.write("2. Voiceover ban raha hai... 🎙️")
                audio_path = create_audio(script, voice_choice)
                
                st.write("3. Pixabay se Aesthetic Video fetch ho raha hai... 🎥")
                video_urls = get_pixabay_videos(topic)
                
                st.write("4. Final Video edit ho raha hai (1-2 min lag sakte hain)... 🎬")
                final_video = assemble_video(audio_path, video_urls, ratio)
                
                if final_video:
                    status.update(label="🎉 Video Ready!", state="complete")
                    st.success("Mubarak ho! Video 100% generate ho gaya!")
                    st.text_area("Generated Script", script, height=120)
                    st.video(final_video)
                else:
                    status.update(label="Error", state="error")
                    st.error("Video rendering me dikkat aayi.")
