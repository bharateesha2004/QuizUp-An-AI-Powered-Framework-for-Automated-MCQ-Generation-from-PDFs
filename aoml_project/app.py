
#steps to run the project
#download the total code folder and open the cmd with the folder path and type "python app.py" and ctrl+left click on the url 
# if api key quota is exausted then run the application again 


import os
from flask import Flask, render_template, request, send_file
import pdfplumber
import docx
import csv
from werkzeug.utils import secure_filename
import google.generativeai as genai
from fpdf import FPDF

# Set your API key
os.environ["GOOGLE_API_KEY"] = "AIzaSyDJPHJ7mNelUISJJRuLSfOtv9qjxlK23Ds"
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("models/gemini-1.5-pro")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['RESULTS_FOLDER'] = 'results/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        with pdfplumber.open(file_path) as pdf:
            text = ''.join([page.extract_text() for page in pdf.pages])
        return text
    elif ext == 'docx':
        doc = docx.Document(file_path)
        text = ' '.join([para.text for para in doc.paragraphs])
        return text
    elif ext == 'txt':
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    return None

def Question_mcqs_generator(input_text, num_questions, difficulty, question_type='mcq'):
    # Define difficulty-specific instructions
    difficulty_instructions = {
        'easy': """
            Generate basic questions that:
            - Focus on direct facts and definitions from the text
            - Use simple and clear vocabulary
            - Have clearly distinct answer choices
            - Test basic recall and understanding
            - Include straightforward concepts
            - Avoid complex analysis or interpretation
        """,
        'medium': """
            Generate intermediate questions that:
            - Include both factual and conceptual understanding
            - Require some analysis and application
            - Have moderately challenging distractors
            - Test application of knowledge
            - Include some inferential thinking
            - Mix direct recall with analytical thinking
        """,
        'hard': """
            Generate challenging questions that:
            - Require deep understanding and critical analysis
            - Include complex scenarios and case studies
            - Have sophisticated and closely related distractors
            - Test evaluation and synthesis of concepts
            - Require integration of multiple concepts
            - Include advanced application and problem-solving
        """
    }

    # Define question type-specific formats and instructions
    question_formats = {
        'mcq': """
            Format each question exactly as follows:
            ## MCQ
            Question: [question]
            A) [option A]
            B) [option B]
            C) [option C]
            D) [option D]
            Correct Answer: [correct option]
            Explanation: [brief explanation]

            Each question should have:
            - A clear, well-formulated question
            - Four distinct answer options (labeled A, B, C, D)
            - The correct answer clearly indicated
            - Distractors (wrong answers) that are plausible but clearly incorrect
            - Answer options of similar length and style
            - The correct answer distributed randomly among options A, B, C, and D
        """,
        'true_false': """
            Format each question exactly as follows:
            ## MCQ
            Question: [clear statement that can be definitively judged as true or false]
            A) True
            B) False
            Correct Answer: [A or B]
            Explanation: [brief explanation with specific reference to the text]

            Each statement should:
            - Be clear and unambiguous
            - Be completely true or completely false
            - Test understanding of key concepts
            - Be based directly on the provided text
            - Include explanation referencing specific parts of the text
        """,
        'fill_blanks': """
            Format each question exactly as follows:
            ## MCQ
            Question: [sentence with _____ for the blank]
            A) [correct answer]
            B) [plausible incorrect option]
            C) [plausible incorrect option]
            D) [plausible incorrect option]
            Correct Answer: A
            Explanation: [brief explanation of why the answer fits the context]

            Each fill-in-the-blank should:
            - Use _____ to indicate the blank
            - Have a single, unambiguous correct answer
            - Focus on key terms or important concepts
            - Include context clues in the sentence
            - Have plausible but clearly incorrect alternatives
        """
    }

    # Construct the main prompt
    prompt = f"""
    You are an AI assistant helping to generate questions based on the following text:
    '{input_text}'

    Difficulty Level: {difficulty.upper()}
    {difficulty_instructions[difficulty]}

    Please generate {num_questions} questions from the text following this format:
    {question_formats[question_type]}

    Ensure that:
    - Questions are relevant to the main concepts in the text
    - Each question tests a different aspect or concept
    - Questions match the specified difficulty level
    - All questions and answers are based strictly on the provided text
    """
    
    response = model.generate_content(prompt).text.strip()
    return response


def save_mcqs_to_file(mcqs, filename):
    results_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    with open(results_path, 'w', encoding='utf-8') as f:
        f.write(mcqs)
    return results_path

def create_pdf(mcqs, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Add title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Generated MCQs", ln=True, align='C')
    pdf.ln(10)
    
    # Reset font for questions
    pdf.set_font("Arial", size=12)

    # Split MCQs and process each question
    for mcq in mcqs.split("## MCQ"):
        if mcq.strip():
            # Add some spacing between questions
            pdf.ln(5)
            
            # Handle lines of the MCQ
            lines = mcq.strip().split('\n')
            for line in lines:
                if line.strip():
                    # Make question text bold
                    if line.startswith("Question:"):
                        pdf.set_font("Arial", 'B', 12)
                    else:
                        pdf.set_font("Arial", size=12)
                    
                    # Add the line with proper spacing
                    pdf.multi_cell(0, 10, line.strip())
            
            # Add extra space after each question
            pdf.ln(5)

    pdf_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    pdf.output(pdf_path)
    return pdf_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_mcqs():
    if 'file' not in request.files:
        return "No file part"

    file = request.files['file']
    difficulty = request.form.get('difficulty', 'medium')
    question_type = request.form.get('question_type', 'mcq')

    if file.filename == '':
        return "No selected file"

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        text = extract_text_from_file(file_path)

        if text:
            try:
                num_questions = int(request.form['num_questions'])
                if num_questions < 1 or num_questions > 50:
                    return "Please enter a number between 1 and 50"
                
                questions = Question_mcqs_generator(text, num_questions, difficulty, question_type)

                txt_filename = f"generated_questions_{filename.rsplit('.', 1)[0]}.txt"
                pdf_filename = f"generated_questions_{filename.rsplit('.', 1)[0]}.pdf"
                
                save_mcqs_to_file(questions, txt_filename)
                create_pdf(questions, pdf_filename)

                os.remove(file_path)

                return render_template('results.html', 
                                    questions=questions,
                                    question_type=question_type,
                                    txt_filename=txt_filename,
                                    pdf_filename=pdf_filename)
            except ValueError:
                return "Please enter a valid number of questions"
            except Exception as e:
                return f"An error occurred: {str(e)}"
        else:
            return "Could not extract text from the file"
    return "Invalid file format"

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    # Create required directories if they don't exist
    for directory in [app.config['UPLOAD_FOLDER'], app.config['RESULTS_FOLDER']]:
        if not os.path.exists(directory):
            os.makedirs(directory)
    
    app.run(debug=True)