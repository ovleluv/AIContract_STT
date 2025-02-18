from flask import Flask, render_template, send_from_directory, jsonify, request, session
from flask_cors import CORS
import os
import openai
import re
import json
import tempfile
from docx import Document
from openai import OpenAI
import subprocess

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# 환경 변수에서 API 키 로드
api_key = os.environ.get("OPENAI_API_KEY")
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

client = OpenAI(api_key=api_key)

# API 키가 설정되지 않았을 경우 에러 처리
if not api_key:
    raise ValueError("OpenAI API key is not set. Check your environment variables.")
else:
    openai.api_key = api_key

contract_types = {
    "Real Estate Lease Agreement": "Documents related to Real Estate Lease Agreement",
    "Power of attorney": "Documents related to power of attorney",
    "Complaint": "Documents related to litigation"
}

contract_data = {}


@app.route('/')
def serve():
    return render_template("index.html")


@app.route('/chat.html')
def chat():
    return render_template("chat.html")


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


def detect_language(text):
    prompt = f"Detect the language of the following text and return only the language code (e.g., 'en', 'ko', 'es', 'fr').\n\n{text}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.3
        )
        detected_language = response.choices[0].message.content.strip()
        session["user_language"] = detected_language

        return detected_language

    except Exception as e:
        print(f"❌ Language detection failed: {str(e)}")
        return "en"  # 기본 언어를 영어로 설정


@app.route('/detect-language', methods=['POST'])
def detect_language_api():
    """검색창에서 입력한 텍스트의 언어를 감지하는 API"""
    data = request.json
    text = data.get('text', '')

    if not text:
        return jsonify({"error": "No text provided."}), 400

    detected_language = detect_language(text)
    return jsonify({"language": detected_language})


# WebM → WAV 변환 함수
def convert_webm_to_wav(input_path):
    try:
        temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        wav_path = temp_wav.name

        command = [
            "ffmpeg", "-i", input_path, "-ac", "1", "-ar", "16000", "-y", wav_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            print(f"❌ FFmpeg conversion failed: {result.stderr.decode()}")
            return None

        return wav_path
    except Exception as e:
        print(f"❌ WebM conversion failed: {str(e)}")
        return None


# 🎤 음성 파일을 업로드하여 Whisper API로 텍스트 변환
@app.route("/stt", methods=["POST"])
def speech_to_text():
    if "file" not in request.files:
        print("❌ Audio file does not arrive at server")
        return jsonify({"error": "❌ Audio file does not arrive at server"}), 400

    file = request.files["file"]

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    temp_file_path = temp_file.name
    file.save(temp_file_path)

    try:
        # 파일 크기 제한 (5MB 초과 시 에러 반환)
        file_size = os.path.getsize(temp_file_path) / (1024 * 1024)
        if file_size > 5:
            return jsonify({"error": "The file size is too large. Please upload under 5MB."}), 400

        # 파일 유효성 검사
        if not os.path.exists(temp_file_path) or os.path.getsize(temp_file_path) == 0:
            print("❌ WebM file is invalid.")
            return jsonify({"error": "WebM file is invalid. Please record again."}), 400

        # WebM → WAV 변환
        wav_path = convert_webm_to_wav(temp_file_path)
        if not wav_path:
            return jsonify({"error": "WebM → WAV conversion failed. Please make sure it is a valid WebM file."}), 400


        # Whisper 변환 시작
        with open(wav_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=""
            )

        transcribed_text = response.text
        detected_language = detect_language(transcribed_text)

        # 계약서 유형 및 필수 항목 분석 추가
        contract_analysis = analyze_contract_data(transcribed_text)

        return jsonify({
            "text": transcribed_text,
            "analysis": contract_analysis,
            "language": detected_language
        })


    except Exception as e:
        print(f"❌ Server error occurred: {str(e)}")
        return jsonify({"error": f"Server error occurred: {str(e)}"}), 500

    finally:
        # 임시 파일 삭제
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


def analyze_contract_data(text):
    prompt = f"""
    There may be one or two people in a conversation.
    If it is two people, understand their relationship well in the conversation.
    Analyze the following conversation to determine the type of contract and information required.
    Please update your information in the appropriate place in your contract.

    대화 내용:
    {text}

    결과 형식:
    {{
        "contract_type": "Contract type",
        "required_fields": ["Required field1", "Required field2", ...]
        "user_information": ["User entry1", "User entry2", ...]
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a contract analysis expert."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.7
    )

    try:
        contract_data = json.loads(response.choices[0].message.content.strip())
        return contract_data
    except json.JSONDecodeError:
        return {"error": "❌ An error occurred while analyzing contract data."}


@app.route('/chatbot-response', methods=['POST'])
def chatbot_response():
    try:
        data = request.json
        user_message = data.get('message', '')
        source = data.get('source', '')
        detected_language = data.get('language', 'en')

        # ✅ 사용자가 처음 입력한 경우, 언어 감지 및 세션 저장
        if "user_language" not in session:
            detected_language = detect_language(user_message)
        else:
            detected_language = session["user_language"]

            # 🔍 사용자가 입력한 키워드를 기반으로 추천 계약서 목록 가져오기
            suggested_contracts = suggest_contracts_list(user_message)

            if not suggested_contracts:
                return jsonify({"error": "❌ No relevant contracts found. Please try again."})

            # 📌 각 추천 계약서별로 필요한 정보 및 예시 샘플 생성
            contract_details = []
            for contract_type in suggested_contracts:
                required_fields = get_contract_required_fields(contract_type)
                contract_content = generate_contract_content(contract_type)

                contract_details.append({
                    "contract_type": contract_type,
                    "required_fields": format_required_fields(required_fields),
                    "contract_sample": contract_content
                })

        response_data = {
            "suggested_contracts": suggested_contracts,
            "contract_details": contract_details,
            "language": detected_language
        }

        return jsonify(response_data)

    except Exception as e:
        return jsonify({"error": f"❌ Server error occurred: {str(e)}"}), 500


def identify_contract_type(user_input):
    """ 사용자의 입력에서 계약서 유형을 감지 """
    for contract in contract_types.keys():
        if contract in user_input:
            return contract
    return None


def suggest_contracts_list(user_input):
    """ 사용자의 입력에서 추천할 계약서 목록을 반환 """
    language = session["user_language"]
    prompt = f"""
    The user entered the following message: '{user_input}'
    Please analyze the message and return a list of the most relevant contract types.
    The response should be formatted as a JSON array with contract types.
    Please respond in '{language}'.

    Example output:
    ["Real Estate Sale Contract", "Vehicle Sale Contract", "Goods Sale Contract"]

    Please respond in JSON format.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a contract recommendation system."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )

        json_match = re.search(r'\[.*\]', response.choices[0].message.content.strip(), re.DOTALL)

        if json_match:
            return json.loads(json_match.group())
        return []

    except Exception:
        return []  # 실패 시 빈 리스트 반환


@app.route('/input-fields', methods=['POST'])
def get_contract_required_fields(contract_type):
    language = session["user_language"]
    prompt = f"'{contract_type}' Provide the input items required to create a contract in a list format. Please respond in '{language}'."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "This is a contract field provision system."},
                      {"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )

        fields_text = response.choices[0].message.content.strip()
        fields_list = fields_text.split("\n")  # ✅ 리스트 변환

        # 🔍 리스트 내부에 `Response` 객체가 있는지 확인하고, 문자열만 남기기
        fields_list = [str(field) for field in fields_list if isinstance(field, str)]

        return fields_list  # ✅ JSON이 아니라 순수한 리스트를 반환

    except Exception as e:
        return []


def generate_contract_content(contract_type, language="en"):
    language = session["user_language"]
    prompt = f"Please fill out a standard contract of ‘{contract_type}’ in {language}." \
             f"Organize it in a way that makes it look nice and present it to you." \
             f"Please respond in {language}."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": " Your are a contract creation assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"❌ Error retrieving contract sample: {str(e)}"


def format_required_fields(required_fields):
    if not isinstance(required_fields, list):
        return "⚠️ Error retrieving required fields."

    # 🔍 `required_fields` 내의 요소가 모두 문자열인지 확인하고 변환
    required_fields = [str(field) for field in required_fields if isinstance(field, str)]

    return "\n".join(required_fields)  # ✅ 문자열이 아닌 데이터는 포함하지 않음


def fill_contract_with_fields(contract, extracted_fields):
    language = session["user_language"]

    prompt = f"""
    Please update the following contract by inserting the provided JSON data in the appropriate locations.
    Ensure the contract remains well-structured and readable.
    Please respond in {language}.

    contract draft:
    {contract}

    JSON data:
    {json.dumps(extracted_fields, ensure_ascii=False)}

    Requirements:
    - Replace placeholders (e.g., [매도인 성명], [매수인 성명]) with corresponding JSON values.
    - If some fields are missing, keep placeholders as they are.
    - Ensure the contract text remains naturally structured.
    - Do not include extra explanatory text such as introductions or conclusions.
    - Only return the updated contract text.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Your are a contract update system."},
                  {"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


@app.route('/download-contract', methods=['POST'])
def download_contract():
    """
    클라이언트에서 특정 계약서 내용을 전달받아 DOCX 파일로 변환 후 다운로드.
    """
    try:
        data = request.get_json()
        contract_type = data.get('contract_type', 'contract')
        contract_text = data.get('contract_text', '')

        if not contract_text:
            return jsonify({"error": "No contract content provided for download."}), 400

        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
            file_path = temp_file.name
            doc = Document()

            # ✅ 계약서 내용을 DOCX 파일에 저장
            doc.add_paragraph(contract_text)
            doc.save(file_path)

        return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path), as_attachment=True,
                                   download_name=f"{contract_type}_contract.docx")

    except Exception as e:
        return jsonify({"error": f"Server error occurred: {str(e)}"}), 500



@app.route('/update-contract', methods=['POST'])
def update_contract():
    try:
        data = request.get_json()
        current_contract = data.get('current_contract', '')
        extracted_fields = data.get('extracted_fields', {})

        if not current_contract or current_contract.strip() == "":
            return jsonify({"error": "❌ Contract details are required."}), 400

        if not extracted_fields or not isinstance(extracted_fields, dict):
            return jsonify({"error": "❌ Extracted field data is required."}), 400

        updated_contract = fill_contract_with_fields(current_contract, extracted_fields)

        return jsonify({"contract": updated_contract})

    except Exception as e:
        print(f"❌ Server error occurred: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500



@app.route("/generate", methods=["POST"])
def generate_contract():
    data = request.get_json()
    selection = data.get('selection')
    extracted_fields = data.get('extracted_fields', {})
    language = session["user_language"]

    if selection not in contract_types:
        return jsonify({"error": "It's a wrong choice. Please select the correct contract type."})

    contract_type = contract_types[selection]
    template_prompt = f"Please fill out a standard contract of ‘{contract_type}’. Please respond in {language}."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": template_prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )

        contract_template = response.choices[0].message.content.strip()

        if extracted_fields:
            update_prompt = f"""
            Please insert the values of the JSON data given in the following contract template into the appropriate positions.
            Please respond in {language}.

            Contract template:
            {contract_template}

            JSON data:
            {json.dumps(extracted_fields, ensure_ascii=False)}

            Requirements:
            1. Insert each field of JSON data into the appropriate position in the contract.
            2. Leave fields without data in the ‘[field name]’ format.
            3. Please maintain the overall format and structure of the contract.
            """

            update_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": update_prompt}
                ],
                max_tokens=1500,
                temperature=0.7
            )

            updated_contract = update_response.choices[0].message.content.strip()
            return jsonify({"contract": updated_contract})

        return jsonify({"contract": contract_template})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/generate', methods=['POST'])
def generate_contract_api():
    data = request.get_json()
    selection = data.get('selection')

    if selection not in contract_types:
        return jsonify({"error": "❌ An error occurred while determining the contract type. Please try again."})

    contract_content, required_fields = generate_contract(selection)

    return jsonify({
        "contract": contract_content,
        "required_fields": required_fields,
        "message": "📌 The information required in the contract is as follows:"
    })


@app.route('/extract-fields', methods=['POST'])
def extract_fields():
    data = request.get_json()
    user_input = data.get('user_input')
    language = session["user_language"]

    prompt = f"""
    Please return the items that should be included in the contract in the following sentence in JSON format:\n"
    "Output must be in valid JSON format. Do not include additional text other than JSON.\n"
        
    The user input is as follows:
    "{user_input}"
    
    Please extract the necessary contract fields from the input and return them in JSON format.
    The response must be a valid JSON object without additional text.

    Example output:
    {{
        "매도인 성명": "홍길동",
        "매수인 성명": "심청이"
    }}
    
    Please respond in {language}."
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a contract field extraction assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )

        extracted_data = response.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', extracted_data, re.DOTALL)

        if json_match:
            json_data = json.loads(json_match.group())
            return jsonify({"extracted_fields": json_data})
        else:
            return jsonify({"error": "❌ No valid JSON data found.", "raw_response": extracted_data})

    except json.JSONDecodeError:
        return jsonify({"error": "❌ OpenAI response is not in valid JSON format."})
    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == '__main__':
    app.run(debug=True)
