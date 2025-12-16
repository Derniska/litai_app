#!/usr/bin/env python
# coding: utf-8
import streamlit as st
import json
import os
import io
import datetime
import urllib.request
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings.yandex import YandexGPTEmbeddings
from langchain_community.chat_models import ChatYandexGPT
from langchain_community.llms import YandexGPT
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS

def read_json(file_path):
    with open(file_path) as file:
        access_data = json.load(file)
    return access_data

@st.cache_resource
def initialize_faiss_vectorstore():
    """
    Vectorstore database initialization.
    
    We use FAISS instead of Chroma in this application.
    
    """
    API_CREDS = read_json(file_path='apicreds.json')
    APP_CONFIG = read_json(file_path='config.json')
    DATA_PATH = f"{APP_CONFIG['docs_db_path']}"
    FAISS_INDEX_PATH = "./faiss_index_full"
    
    embeddings = YandexGPTEmbeddings(
            api_key = API_CREDS['api_key'],
            folder_id = API_CREDS['folder_id'],
            sleep_interval = .1
        )
    
    # If index exists...
    if os.path.exists(FAISS_INDEX_PATH):
        with st.spinner('Loading FAISS index...'):
            vectorstore = FAISS.load_local(
                FAISS_INDEX_PATH, 
                embeddings, 
                allow_dangerous_deserialization=True
            )
            st.success("FAISS index loaded")
            return vectorstore, API_CREDS
    
    # ...or create new index
    with st.spinner('Documents are loading...'):

        loader = DirectoryLoader(
            DATA_PATH, 
            glob="**/*.pdf", 
            loader_cls=PyMuPDFLoader,
            show_progress=True, 
            use_multithreading=True
        )
        docs = loader.load()
    
    
    with st.spinner('Processing documents...'):
        
        text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,  
                chunk_overlap=200  
            )
        splits = text_splitter.split_documents(docs)
    
    with st.spinner('Creating FAISS index...'):
        vectorstore = FAISS.from_documents(splits, embeddings)
        vectorstore.save_local(FAISS_INDEX_PATH)
        st.success("FAISS index created and saved")
    
    return vectorstore, API_CREDS

def get_rag_chain(vectorstore, template, temperature, k_max, api_creds):
    """
    RAG initialization with input parameters.
    
    Args:
      :vectorstore:
      :template:
      :temperature:
      :k_max:
      :api_creds:

    Returns:
      RAG chain instance
    
    """
    
    retriever = vectorstore.as_retriever(
            search_type = 'similarity',
            search_kwargs={"k": k_max}
        )
    prompt = PromptTemplate.from_template(template) 
    llm =  YandexGPT(
        name="yandexgpt",
        api_key = api_creds['api_key'], 
        folder_id = api_creds['folder_id'],
        temperature = temperature
    )
    rag_chain = rag_chain =  (
            {"context": retriever, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )

    return rag_chain

if 'vectorstore_full' not in st.session_state:
    st.session_state.vectorstore_full, st.session_state.api_creds = initialize_faiss_vectorstore()

st.set_page_config(
    page_title="Articles analysis with AI",
    page_icon="💬"
)
st.sidebar.header('Chat-bot with LLM')
st.header('AI assitant for RAG-based economic litrature search and review', divider='rainbow')
st.write("#### Documents analysis")
st.markdown("""
In this secion can study the selected papers from the database in more detail. 
Enter titles of interesting papers in the field below   
Each paper will be available for:
- 📖 Full text analysis
- 🔍 Methodology extraction
- 📊 Results comparison
- 📝 Notes & annotations

Pose specific questions about these papers to get AI-powered insights
""")

default_instruction = (
    "Use the following pieces of context to answer the question at the end. "
    "If you don't know the answer, just say that you don't know, don't try to make up an answer. "
    "Use three sentences maximum and keep the answer as concise as possible. "
    "Always say \"thanks for asking!\" at the end of the answer. \n"
    "Context: {context}\n"
    "Question: {question}\n"
    "Answer: "
)

st.write('#### Give a prompt')
template = st.text_area(
    'Input prompt for chat-bot',
    default_instruction
)

st.write('#### Temperature for bot')
st.write(
    """
    The higher the value of this parameter, the more creative
    and random the model's responses will be. Accepts values
    from 0 (inclusive) to 1 (inclusive).
    Default value: 0 (no creativity)
    """
)
temperature = st.slider("Input temperature for chat-bot", .0, 1., .0, .1)

st.write('#### Enter the number of relevant documents')
st.write(
    """
    You need to specify the maximum number of documents in a single
    search to limit the search scope for the chat-bot.
    Default value: 3 documents
    """
)
k_max = st.slider('Enter the number of documents', 1, 5, 3)

rag_chain = get_rag_chain(
    st.session_state.vectorstore_full, 
    template, 
    temperature, 
    k_max, 
    st.session_state.api_creds
)

st.write('#### Ask chat-bot your questions')

if 'messages' not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message['role']):
        st.markdown(message['content'])

if query := st.chat_input('Enter your message'):
    st.chat_message('user').markdown(query)
    st.session_state.messages.append(
        {
            'role': 'user',
            'content': query
        }
    )
    
    answer = rag_chain.invoke(query)
    with st.chat_message('assistant'):
        st.markdown(answer)
    st.session_state.messages.append(
        {
            'role': 'assistant',
            'content': answer
        }
    )
