Steps to run
1. ollama pull llama3 
2. ollama pull nomic-embed-text
3. ollama serve
4. Install requirements in requirements.txt using pip(tested on python 3.11)
5. Gemini api key will likely be expired, replace it in backend/gemini_live.py
6. In backend folder,uvicorn main:app --reload
7. In frontend folder, click on index.html {tested on chromium and firefox} 
8. For the live page, run https://localhost:8000/live {tested on chromium and firefox}
