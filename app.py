import streamlit as st
import os
import requests
import re
import urllib.parse
import subprocess
import imageio_ffmpeg
import google.generativeai as genai

# ================= K E Y S (PRE-CONFIGURED) =================
GEMINI_KEY = "AQ.Ab8RN6JD7UflDlIwhNt6sZVcwhz1gLg4u5j9OWrOsLN8Pf8OnA"
PIXABAY_API_KEY = "57871281-bac58345c5fba7b07f0655556"

# ================= 1. GEMINI 3.6 FLASH SCRIPT =================
def generate_script(topic, duration):
    target_words = int(duration) * 2
    prompt = (
        f"Write a voiceover script about '{topic}'. "
        f"Language: Hinglish. Length: strictly around {target_words} words. "
        f"Only return spoken plain text. Strictly NO emojis, NO hashtags, NO asterisks, NO markdown."
    )
    
    # Method 1: Google GenAI SDK (gemini-3.6-flash)
    try:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel('gemini-3.6-flash')
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
    except Exception:
        pass

    # Method 2: Direct REST API (with API Key query)
    models_to_try = ['gemini-3.6-flash', 'gemini-1.5-flash', 'gemini-2.0-flash']
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_KEY}"
        try:
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
        except Exception:
            continue

    # Method 3: Direct REST API (with Bearer Token authorization header)
    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GEMINI_KEY}"
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
        except Exception:
            continue

    return "Error: Gemini Script generate nahi ho payi. Key access verify karein."

# ================= 2. VOICEOVER ENGINE =================
def create_audio(text, voice_choice, output_file="voiceover.mp3"):
    clean = re.sub(r'[^\w\s.,?!।\'-]', ' ', text).strip()
    words = clean.split()
    if not words:
        words = ["Video", "shuru", "ho", "raha", "hai"]
    
    lang = "en-IN" if "Male" in voice_choice else "hi"
    
    chunks = []
    curr = ""
    for w in words:
        if len(curr) + len(w) + 1 <= 95:
            curr += (" " if curr else "") + w
        else:
            if curr:
                chunks.append(curr)
            curr = w
    if curr:
        chunks.append(curr)
        
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    audio_data = bytearray()
    
    for chunk in chunks:
        q = urllib.parse.quote(chunk)
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={q}&tl={lang}&client=tw-ob"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200 and len(res.content) > 50:
                audio_data.extend(res.content)
            else:
                fallback_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={q}&tl=hi&client=tw-ob"
                fb_res = requests.get(fallback_url, headers=headers, timeout=10)
                if fb_res.status_code == 200:
                    audio_data.extend(fb_res.content)
        except Exception:
            continue
            
    if len(audio_data) > 100:
        with open(output_file, "wb") as f:
            f.write(audio_data)
        return output_file
        
    with open(output_file, "wb") as f:
        f.write(b'\xff\xfb\x90\x44' * 500)
    return output_file

# ================= 3. PIXABAY VIDEO SEARCH =================
def get_pixabay_videos(user_topic):
    clean_topic = user_topic.strip()
    search_terms = [clean_topic, clean_topic.split()[0], "nature aesthetic"]
    
    for term in search_terms:
        params = {
            "key": PIXABAY_API_KEY,
            "q": term,
            "per_page": 5,
            "safesearch": "true"
        }
        try:
            res = requests.get("https://pixabay.com/api/videos/", params=params, timeout=10)
            if res.status_code == 200:
                hits = res.json().get("hits", [])
                urls = []
                for hit in hits:
                    vids = hit.get("videos", {})
                    for qual in ["large", "medium", "small"]:
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

# ================= 4. FAST FFMPEG VIDEO COMPOSER =================
def assemble_video_ffmpeg(audio_path, video_urls, ratio):
    if not video_urls:
        return None
        
    raw_video = download_video(video_urls[0], "bg_video.mp4")
    output_video = "final_output.mp4"
    
    if ratio == "9:16 (Shorts)":
        scale_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:
        scale_filter = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"
        
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    cmd = [
        ffmpeg_exe,
        "-y",
        "-stream_loop", "-1",
        "-i", raw_video,
        "-i", audio_path,
        "-shortest",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-vf", scale_filter,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        output_video
    ]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(output_video) and os.path.getsize(output_video) > 1000:
        return output_video
    return None

# ================= UI =================
st.set_page_config(page_title="My Video Maker", page_icon="🎬", layout="centered")
st.title("🎬 My Free Video Maker")

topic = st.text_input("1. Video Topic", placeholder="Aesthetic weather, Gym motivation, Sports car...")
ratio = st.radio("2. Ratio", ["9:16 (Shorts)", "16:9 (YouTube)"])
duration = st.slider("3. Duration (sec)", 10, 30, 15, 5)
voice_choice = st.radio("4. Voiceover", ["Male Hinglish", "Female Hinglish"])

if st.button("🚀 Generate Video", type="primary"):
    if not topic:
        st.warning("Pehle koi topic likhein!")
    else:
        with st.status("Video process ho raha hai...", expanded=True) as status:
            st.write("1. Gemini 3.6 Flash Script likh raha hai... ✍️")
            script = generate_script(topic, duration)
            
            if script.startswith("Error:"):
                status.update(label="Script Error", state="error")
                st.error(script)
            else:
                st.write("2. Voiceover generate ho raha hai... 🎙️")
                audio_path = create_audio(script, voice_choice)
                
                st.write(f"3. Pixabay se '{topic}' ki HD video fetch ho rahi hai... 🎥")
                video_urls = get_pixabay_videos(topic)
                
                if not video_urls:
                    status.update(label="No Video Found", state="error")
                    st.error(f"Pixabay par '{topic}' ki video nahi mili. Thoda simple topic try karein.")
                else:
                    st.write("4. Video aur Audio ko merge kiya ja raha hai... 🎬")
                    final_video = assemble_video_ffmpeg(audio_path, video_urls, ratio)
                    
                    if final_video:
                        status.update(label="🎉 Video Ready!", state="complete")
                        st.success("Aapka video successfully ready ho gaya!")
                        st.text_area("Generated Script", script, height=120)
                        st.video(final_video)
                        with open(final_video, "rb") as file:
                            st.download_button(
                                label="⬇️ Download Video (MP4)",
                                data=file,
                                file_name="generated_video.mp4",
                                mime="video/mp4"
                            )
                    else:
                        status.update(label="Error", state="error")
                        st.error("Video merge hone mein dikkat aayi.")
