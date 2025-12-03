from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# In-memory storage for answers (persists only during app runtime)
stored_answers = []

# Hardcoded list of survey questions
QUESTIONS = [
    {"id": 1, "text": "What is your name?"},
    {"id": 2, "text": "How old are you?"},
    {"id": 3, "text": "What is your favorite programming language?"}
]

@app.route('/')
def index():
    # Serve the main HTML page
    return render_template('index.html')

@app.route('/questions', methods=['GET'])
def get_questions():
    # Return the fixed list of questions as JSON
    return jsonify(QUESTIONS)

@app.route('/answers', methods=['GET'])
def get_answers():
    # Return all stored answers as JSON
    return jsonify(stored_answers)

@app.route('/answers', methods=['POST'])
def submit_answers():
    # Receive JSON payload like { "answers": [{ "questionId": 1, "answer": "Alice" }, ...] }
    data = request.get_json()
    # Append to in-memory storage
    stored_answers.append(data)
    # Return success response
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    # Run the app in debug mode for local development
    app.run(debug=True)
