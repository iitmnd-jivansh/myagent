Steps to run
1. ollama pull llama3 
2. ollama pull nomic-embed-text
3. ollama serve
4. Install requirements in requirements.in using pip(tested on python 3.11)
5. In backend folder, uvicorn main:app --reload
6. In frontend folder, python -m http.server 3000
7. visit http://localhost:3000

