import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
import datetime
from pymongo.errors import ConnectionFailure

load_dotenv()

app = Flask(__name__)

# ElevenLabs API configuration
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# MongoDB connection with error handling
def get_mongodb_client():
    try:
        mongodb_uri = os.getenv('MONGODB_URI')
        if not mongodb_uri:
            raise ValueError("MONGODB_URI environment variable is not set")
        
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        # Test the connection
        client.admin.command('ping')
        return client
    except ConnectionFailure as e:
        print(f"Could not connect to MongoDB: {e}")
        return None
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

# Initialize MongoDB connection
client = get_mongodb_client()
if client:
    db = client['yipibear']
    subscribers = db['subscribers']
else:
    print("Warning: MongoDB connection failed. Subscription feature will not work.")

# Define constants
GEMINI_MODEL = "gemini-2.0-flash"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
MAX_RETRIES = 3
DELAY_MS = 2000  # Delay between retries in milliseconds

# Common emotional challenges
EMOTIONAL_CHALLENGES = [
    "Anxiety",
    "Low Confidence",
    "Grief",
    "Separation Anxiety",
    "Social Anxiety",
    "Anger Management",
    "Fear of Failure",
    "Bullying",
    "Making Friends",
    "Self-Esteem"
]

# Utility function to call the Gemini API
def call_gemini_api(model: str, prompt: str) -> str:
    try:
        gemini_api_key = os.getenv('API_KEY')
        response = requests.post(
            f"{API_URL}?key={gemini_api_key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "topK": 40, "topP": 0.8}
            },
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    except Exception as e:
        print(f"Error during API call: {e}")
        return "Error generating story."


# Step 1: Story Generator Agent
def generate_story(specification: str) -> str:
    prompt = f"""
    Please generate a short therapeutic story for children aged 5-8 years old who experience the issue mentioned.
    The story should feature a relatable child character who experiences feelings of worry or fear related to this situation. The narrative should gently introduce a simple coping mechanism or positive way of thinking that the character can use to manage their feelings.

    Please use clear and simple language, incorporating a comforting and encouraging tone. The story should include a clear beginning, a moment where the character experiences the problem, the introduction and use of the coping strategy, and a hopeful or positive resolution where the child feels more empowered or comfortable.

    Feel free to use age-appropriate metaphors or analogies to explain anxiety or the coping mechanism. The story should be approximately 300-500 words and have a title that reflects the theme of the story.

    Avoid overly complex plots or scary scenarios. The focus should be on providing comfort, validation, and a sense of possibility for managing feelings.

    Specification: {specification}
    
    Don't give a title to the story.
    """
    return call_gemini_api(GEMINI_MODEL, prompt)


# # Step 2: Story Reviewer Agent
# def review_story(generated_story: str) -> str:
#     prompt = f"""
#     You are an expert story editor. You should vet the stories to make sure that they are kid-friendly and easy to understand.
#     Here is the story:
#     ```python
#     {generated_story}
#     ```
#     Please provide feedback on how to improve the story, ensuring that it is comforting, clear, and suitable for children.
#     """
#     print(prompt)
#     return call_gemini_api(GEMINI_MODEL, prompt)


# # Step 3: Story Polish Agent
# def polish_story(review_comments: str) -> str:
#     prompt = f"""
#     You are an expert story generation agent that takes feedback and writes good therapeutic stories for children.
#     Take the feedback provided by the story reviewer and generate a new story based on it.
#     ```python
#     {review_comments}
#     ```
#     Please rewrite the story based on the feedback, improving clarity, comfort, and appropriateness for children. Please return just the story and it's title and nothing else.
#     """
#     print(prompt)
#     return call_gemini_api(GEMINI_MODEL, prompt)


# Step 4: Orchestrating the Pipeline
@app.route("/generate", methods=["POST"])
def generate_story_pipeline():
    specification = request.json.get("specification")

    # Step 1: Generate the initial story
    generated_story = generate_story(specification)

    # # Step 2: Review the generated story
    # review_comments = review_story(generated_story)

    # # Step 3: Polish the story based on review comments
    # polished_story = polish_story(review_comments)

    return jsonify({"story": generated_story})


@app.route("/")
def index():
    return render_template("index.html", challenges=EMOTIONAL_CHALLENGES)

@app.route("/subscribe", methods=["POST"])
def subscribe():
    if not client:
        return jsonify({"success": False, "error": "Database connection error"})
        
    name = request.form.get("name")
    email = request.form.get("email")
    
    if name and email:
        try:
            subscribers.insert_one({
                "name": name,
                "email": email,
                "timestamp": datetime.datetime.now()
            })
            return jsonify({"success": True})
        except Exception as e:
            print(f"Error inserting subscriber: {e}")
            return jsonify({"success": False, "error": "Database error"})
    return jsonify({"success": False, "error": "Missing name or email"})

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/story-form")
def story_form():
    return render_template("story_form.html", challenges=EMOTIONAL_CHALLENGES)

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/text-to-speech", methods=["POST"])
def text_to_speech():
    try:
        data = request.json
        text = data.get('text')
        voice_id = data.get('voice_id')

        if not text or not voice_id:
            return jsonify({"error": "Missing text or voice_id"}), 400

        # Call ElevenLabs API
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }

        body = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.75,
                "style": 0.5,
                "use_speaker_boost": True
            }
        }

        response = requests.post(
            f"{ELEVENLABS_API_URL}/{voice_id}",
            json=body,
            headers=headers
        )

        if response.status_code != 200:
            return jsonify({"error": "Failed to generate speech"}), 500

        # Return the audio file
        return Response(
            response.content,
            mimetype="audio/mpeg",
            headers={"Content-Disposition": "attachment;filename=story.mp3"}
        )

    except Exception as e:
        print(f"Error in text-to-speech: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
