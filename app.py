from flask import Flask, render_template, send_from_directory, jsonify, request
from flask_cors import CORS
import os
import openai
import re
import json
from docx import Document

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# 환경 변수에서 API 키 로드
api_key = os.environ.get("OPENAI_API_KEY")

# API 키가 설정되지 않았을 경우 에러 처리
if not api_key:
    raise ValueError("OpenAI API 키가 설정되지 않았습니다. 환경 변수를 확인하세요.")
else: openai.api_key = api_key

contract_types = {
    "1": "부동산임대차계약서",
    "2": "위임장",
    "3": "소장"
}

@app.route('/')
def serve():
    return render_template('index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)

@app.route("/stt", methods=["POST"])
def speech_to_text():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    response = openai.Audio.transcribe("whisper-1", file)
    return jsonify({"text": response["text"]})

@app.route('/select', methods=['POST'])
def select():
    data = request.get_json()
    selection = data.get('selection')

    if selection in contract_types:
        response = f"선택하신 계약서는 '{contract_types[selection]}'입니다. 이어지는 계약서 예시 샘플을 확인해 주세요."
    else:
        response = "잘못된 선택입니다. 1, 2, 3 중에서 선택해 주세요."

    return jsonify({"message": response})

@app.route('/generate', methods=['POST'])
def generate_contract():
    data = request.get_json()
    selection = data.get('selection')
    extracted_fields = data.get('extracted_fields', {})

    if selection not in contract_types:
        return jsonify({"error": "잘못된 선택입니다. 1, 2, 3 중에서 선택해 주세요."})

    contract_type = contract_types[selection]
    template_prompt = f"'{contract_type}'의 표준 계약서를 작성해 주세요."

    try:
        template_response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": template_prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        contract_template = template_response.choices[0].message.content.strip()

        if extracted_fields:
            update_prompt = f"""
            다음 계약서 템플릿에 주어진 JSON 데이터의 값들을 적절한 위치에 삽입해주세요.

            계약서 템플릿:
            {contract_template}

            JSON 데이터:
            {json.dumps(extracted_fields, ensure_ascii=False)}

            요구사항:
            1. JSON 데이터의 각 필드를 계약서의 적절한 위치에 삽입해주세요.
            2. 데이터가 없는 필드는 '[필드명]' 형식으로 남겨두세요.
            3. 계약서의 전체적인 형식과 구조는 유지해주세요.
            """

            update_response = openai.chat.completions.create(
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

@app.route('/update-contract', methods=['POST'])
def update_contract():
    data = request.get_json()
    current_contract = data.get('current_contract', '')
    extracted_fields = data.get('extracted_fields', {})

    if not current_contract or not extracted_fields:
        return jsonify({"error": "계약서 내용과 필드 데이터가 필요합니다."})

    try:
        update_prompt = f"""
        다음 계약서의 내용을 주어진 JSON 데이터를 이용해 업데이트해주세요.

        현재 계약서:
        {current_contract}

        JSON 데이터:
        {json.dumps(extracted_fields, ensure_ascii=False)}
        """

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": update_prompt}
            ],
            max_tokens=1500,
            temperature=0.7
        )
        updated_contract = response.choices[0].message.content.strip()
        
        # Word 파일 생성
        doc = Document()
        doc.add_paragraph(updated_contract)
        file_path = 'completed_contract.docx'
        doc.save(file_path)

        return jsonify({"contract": updated_contract, "file_path": file_path})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/input-fields', methods=['POST'])
def get_input_fields():
    data = request.get_json()
    selection = data.get('selection')

    if selection not in contract_types:
        return jsonify({"error": "잘못된 선택입니다. 1, 2, 3 중에서 선택해 주세요."})

    contract_type = contract_types[selection]
    prompt = f"'{contract_type}'의 내용을 기반으로 중요한 입력 항목 5~10개를 추출해 주세요."

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        fields_text = response.choices[0].message.content.strip()
        fields = fields_text.split('\n')

        request_message = f"'{contract_type}'을 작성하기 위해 다음 항목을 입력해 주세요:\n\n"
        for field in fields:
            request_message += f"- {field}\n"

        return jsonify({"message": request_message})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/extract-fields', methods=['POST'])
def extract_fields():
    data = request.get_json()
    user_input = data.get('user_input')

    prompt = (
        "다음 문장에서 계약서에 포함되어야 할 항목을 JSON 형태로 반환해 주세요:\n"
        "반드시 유효한 JSON 형식으로 출력해야 합니다. JSON 외의 추가적인 텍스트를 포함하지 마세요."
        f"문장: {user_input}"
    )

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        extracted_data = response.choices[0].message.content.strip()
        # JSON 형태의 데이터만 추출
        json_match = re.search(r'\{.*\}', extracted_data, re.DOTALL)
        
        if json_match:
            json_data = json.loads(json_match.group())  # JSON 변환
            return jsonify({"extracted_fields": json_data})
        else:
            return jsonify({"error": "응답에서 유효한 JSON 데이터를 찾을 수 없습니다.", "raw_response": extracted_data})

    except json.JSONDecodeError:
        return jsonify({"error": "OpenAI 응답이 유효한 JSON 형식이 아닙니다."})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/download', methods=['GET'])
def download_contract():
    file_path = 'completed_contract.docx'
    if os.path.exists(file_path):
        return send_from_directory('.', file_path, as_attachment=True)
    else:
        return jsonify({"error": "다운로드할 파일이 없습니다."})

if __name__ == '__main__':
    app.run(debug=True)
