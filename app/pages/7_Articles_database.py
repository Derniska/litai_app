#!/usr/bin/env python
# coding: utf-8

import os
import io
import json
import datetime
import streamlit as st
from pathlib import Path
import fitz
from PIL import Image

def read_json(file_path):
    with open(file_path) as file:
        access_data = json.load(file)
    return access_data

# Page configuration
st.set_page_config(
    page_title='Articles Database', 
    page_icon='📚'
)
st.sidebar.header('Articles Database')
st.header('Database contains downloaded research articles', divider='rainbow')

st.markdown(
    f"""
    Here you can view all downloaded articles (PDF files) 
    and manage your research library.
    """
)
st.divider()

APP_CONFIG = read_json(file_path='config.json')
ARTICLES_PATH  = APP_CONFIG.get('docs_db_path')
st.write(ARTICLES_PATH)

@st.cache_data
def get_articles_data(path):
    """Get all PDF files from the articles directory"""
    pdf_files = [
        f for f in os.listdir(path) 
        if f.lower().endswith('.pdf')
    ]
    
    articles = []
    for f in pdf_files:
        file_path = os.path.join(path, f)
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
        created_time = datetime.datetime.fromtimestamp(os.path.getctime(file_path))
        
        articles.append({
            'file_name': f,
            'title': f.replace('.pdf', '').replace('_', ' '),
            'file_path': file_path,
            'size_mb': round(file_size, 2),
            'created': created_time.strftime('%Y-%m-%d %H:%M:%S'),
            'file_size_bytes': os.path.getsize(file_path)
        })
    
    # Sort by creation date (newest first)
    articles.sort(key=lambda x: x['created'], reverse=True)
    return articles

# Display articles gallery
st.write('#### Articles Library')

# Get articles
articles_list = get_articles_data(path=ARTICLES_PATH)
N_COLS = 3
n_cols = st.slider('Width:', min_value=1, max_value=5, value=N_COLS)
cols = st.columns(n_cols)
for i, doc in enumerate(articles_list):
    with cols[i % n_cols]:
        pdf_document = fitz.open(doc['file_path'])
        
        # Конвертируем первую страницу в изображение
        page = pdf_document[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Увеличиваем разрешение
        
        # Конвертируем в PIL Image
        img_data = pix.tobytes("ppm")
        img = Image.open(io.BytesIO(img_data))
        
        # Показываем изображение
        st.image(
            img,
            caption=f"{doc['title']}\n📅 {doc['created']} | 📦 {doc['size_mb']} MB",
            use_container_width=True
        )
        with open(doc['file_path'], 'rb') as f:
            pdf_bytes = f.read()
        
        st.download_button(
            label="⬇️ Download PDF",
            data=pdf_bytes,
            file_name=doc['file_name'],
            mime="application/pdf",
            key=f"dl_{i}"
        )
        
        pdf_document.close()
st.divider()