from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import random
import feedparser
import torch
import requests
from transformers import AutoModelForCausalLM, AutoTokenizer
from datetime import datetime, timedelta

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')

model_name = "HuggingFaceTB/SmolLM2-135M-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

def get_db_connection():
    connection = sqlite3.connect('project.db')
    connection.row_factory = sqlite3.Row
    return connection

def generate_punchy_title(abstract_text):
    system_prompt = (
        "You are a sharp, conversational science journalist. Your task: craft a punchy, "
        "engaging title for this research. Just the title, no preamble."
    )
    user_prompt = f"Create a short, catchy title for this: {abstract_text[:800]}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    formatted_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(formatted_prompt, return_tensors="pt")
    
    with torch.no_grad():
        output_tokens = model.generate(**inputs, max_new_tokens=40, temperature=0.7)
    
    full_text = tokenizer.decode(output_tokens[0], skip_special_tokens=True)
    ai_response = full_text.split("assistant")[-1].strip() if "assistant" in full_text else full_text.strip()
    
    for junk in ["[", "]", "(", ")", "*", "#", '"', "Title:"]:
        ai_response = ai_response.replace(junk, "")
            
    return ai_response.strip()

def generate_simple_analogy(abstract_text):
    system_prompt = (
        "You are a sharp, conversational science journalist. Your task: explain this research "
        "using a simple, everyday-life analogy. Just the analogy, no preamble."
    )
    user_prompt = f"Break this down using a clear analogy: {abstract_text[:800]}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    formatted_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(formatted_prompt, return_tensors="pt")
    
    with torch.no_grad():
        output_tokens = model.generate(**inputs, max_new_tokens=120, temperature=0.7)
    
    full_text = tokenizer.decode(output_tokens[0], skip_special_tokens=True)
    ai_response = full_text.split("assistant")[-1].strip() if "assistant" in full_text else full_text.strip()
    
    intros = ["here is a simple analogy", "here's a simple analogy", "this research is like"]
    for intro in intros:
        if ai_response.lower().startswith(intro):
            ai_response = ai_response[len(intro):].strip().lstrip(":").strip()

    for junk in ["[", "]", "(", ")", "*", "#", '"', "Analogy:", "Summary:"]:
        ai_response = ai_response.replace(junk, "")
            
    return ai_response.strip()

def fetch_and_store_new_paper(topic='cs.AI'):
    random_start_index = random.randint(0, 50)
    api_url = f"http://export.arxiv.org/api/query?search_query=cat:{topic}&start={random_start_index}&max_results=1"
    
    try:
        response = requests.get(api_url, timeout=10)
        feed = feedparser.parse(response.text)
        
        if feed.entries:
            paper = feed.entries[0]
            abstract = paper.summary
            catchy_title = generate_punchy_title(abstract)
            simple_analogy = generate_simple_analogy(abstract)
            
            db = get_db_connection()
            db.execute('INSERT INTO papers (title, summary, link) VALUES (?, ?, ?)', (catchy_title, simple_analogy, paper.link))
            db.commit()
            db.close()
            return True
    except:
        return False
    return False

@app.route('/')
def home():
    db = get_db_connection()
    papers = db.execute('SELECT * FROM papers ORDER BY id DESC LIMIT 10').fetchall()
    
    if not papers:
        fetch_and_store_new_paper()
        papers = db.execute('SELECT * FROM papers ORDER BY id DESC LIMIT 10').fetchall()
    
    latest_paper = papers[0] if papers else None
    latest_id = latest_paper['id'] if latest_paper else 0
    current_notification = f"New Discovery: {latest_paper['title']}" if latest_paper else "Welcome to Morning Muses"
    notification_body = latest_paper['summary'][:100] + "..." if latest_paper else "Your research companion is ready."
        
    db.close()
    return render_template('index.html', papers=papers, notification_title=current_notification, notification_body=notification_body, latest_id=latest_id)

@app.route('/fetch', methods=['POST'])
def manual_fetch():
    selected_topic = request.form.get('topic', 'cs.AI')
    fetch_and_store_new_paper(selected_topic)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)