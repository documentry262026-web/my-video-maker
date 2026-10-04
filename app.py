import streamlit as st
import edge_tts
import os
import asyncio
import requests
import google.generativeai as genai
from moviepy.editor import VideoFileClip, AudioFileClip, vfx

API_KEYS = [
    "AQ.Ab8RN6Jb3y0erqnciAMRCusCyaMHCluce0WxZT3LgqumT_T25g",
    "AQ.Ab8RN6JcUjFt1arWGHmHwe-ojDdME_l4Y0g2PTb3U68m0ZmnTg",
    "AQ.Ab8RN6IAm1fDDXSVKRiOfKolqq6WstM27G6JoCzUknR08IyP9w"
]
PINTEREST_TOKEN = "pina_AMAXVNAYAAZESBIAGAAGCD617W3QFIIBACGSPAWX3VG25LPYTPNGSWWJNNFMJBKIYX220ZMIWADURZLCPB5LILLQLUPLKCQA"

def generate_script(topic, duration):
    target_words = int(duration) * 2
    prompt = f"Write a voiceover script about '{topic}'. Language: Hinglish. Length: {target_words} words. Only return the spoken script text, no formatting."
    for key in API_KEYS:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-3.6-flash')
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            continue
    return "Error"

async def create_audio(text, voice):
    output_file = "voiceover.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
    return output_file

def get_pinterest_videos(query):
    url = "https://api.pinterest.com/v5/search/partner/pins"
    headers = {"Authorization": f"Bearer {PINTEREST_TOKEN}", "Content-Type": "application/json"}
    params = {"term": query, "country_code": "US"}
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        video_urls = []
        for pin in data.get("items", []):
            media = pin.get("media", {})
            if "videos_list" in media:
                best = list(media["videos_list"].values())[-1]
                if "url" in best: video_urls.append(best["url"])
            elif "video_url" in pin:
                video_urls.append(pin.get("video_url"))
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

topic = st.text_input("1. Topic", placeholder="Aesthetic tech setup, Gym workout...")
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
            
            if script == "Error":
                status.update(label="Error", state="error")
                st.error("AI Script fail ho gayi.")
            else:
                st.write("2. Voiceover ban raha hai... 🎙️")
                voice_id = "hi-IN-MadhurNeural" if "Male" in voice_choice else "hi-IN-SwaraNeural"
                audio_path = asyncio.run(create_audio(script, voice_id))
                
                st.write("3. Pinterest se Video aa raha hai... 📌")
                video_urls = get_pinterest_videos(topic)
                
                if not video_urls:
                    status.update(label="Partial Success", state="complete")
                    st.warning("Pinterest Video nahi mila. Sirf Audio sun lo.")
                    st.audio(audio_path)
                else:
                    st.write("4. Final Video edit ho raha hai (is process mein 1-2 min lagenge)... 🎬")
                    final_video = assemble_video(audio_path, video_urls, ratio)
                    
                    status.update(label="🎉 Video Ready!", state="complete")
                    st.success("Video successfully generate ho gaya!")
                    st.text_area("Generated Script", script, height=150)
                    st.video(final_video)
