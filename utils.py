from cryptography.fernet import Fernet
from bs4 import BeautifulSoup

import streamlit as st
import html2text
import requests
import socket
import json
import os
import re

#######################################################################################################################
### Init Methods

def init_lang():
	text_all_languages = json.load(open('languages.json','r'))
	st.session_state['text_fields'] = text_all_languages[st.session_state['lang']]

def init_models():
	# Load the model json file
	with open('model_params.json.crypt', 'rb') as file:
		enc = file.read()
	fernet_coder = Fernet(os.environ["fernet_key"].encode('utf-8'))
	model_params_all = json.loads(fernet_coder.decrypt(enc))

	st.session_state['model'] = model_params_all[st.session_state['lang']]
	st.session_state['job_question'] = model_params_all['job']


#########################################################################################################################
### Helper functions

def to_color(state):
    if state:
        return 'primary'
    else:
        return 'secondary'


def reset_buttons():
	st.session_state['btn_thup'] = 10*[False]
	st.session_state['btn_thdn'] = 10*[False]


def not_blank_rating():
	partial1 = ( True in st.session_state['btn_thup']) 
	partial2 = ( True in st.session_state['btn_thdn']) 
	return (partial1 or partial2)


def cycle():
	st.session_state['counter'] = st.session_state['counter'] + 1
	st.session_state['counter'] = st.session_state['counter'] % st.session_state['mod']


def get_and_store_serverIP():
    # Get the server IP and encode it
	st.session_state['server_IP'] = socket.gethostbyname(socket.gethostname())
	fernet = Fernet(os.environ["fernet_key"].encode('utf-8'))
	st.session_state['encoded_server_IP'] = fernet.encrypt(st.session_state['server_IP'].encode('utf-8'))


def acceptable_input(input):
	return all((x.isalnum() or x.isspace() or x == '_' or x == '-') for x in input)


def render_acceptable(input):
	return "".join([x for x in input if (x.isalnum() or x.isspace() or x == '_' or x == '-')])


#########################################################################################################################
### Functions associated with downloading job ads

def url_detector(input: str):
    if 'http' in input:
        if 'intervieweb.it' in input:
            return re.search(r'(https?://[^\s]+)', input).group(0)
        else:
            st.toast("We currently support only Inrecruting vacancy parsing.")
        return None
    return None


def url_2_text(url: str):
    HEADERS = {'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'}
    answer = requests.get(url, headers=HEADERS)
    bs = BeautifulSoup(answer.text, features='html.parser')
    if len(bs.find_all('h3', {'class':'body__headings'})) != 4:
        return None
    else:
        headers = [a.text for a in bs.find_all('h3', {'class':'body__headings'})]
        insides = [html2text.html2text(str(b)) for b in bs.find_all('div', {'class':'body__text'})]
        return (headers[1:3],insides[1:3])

#########################################################################################################################
### Functions associated with postoprocessing

def clean_text(text):
    text = text.rstrip().lstrip().replace('#','')
    indices = [i for i, chr in enumerate(text) if chr in '1234567890']
    suitable = [index for index in indices if (text[index+1] == '.') or (text[index+1] == ')')]
    if len(suitable) == 0:
         return [""]
    
    for i in range(len(suitable)):
        if suitable[i] == 0:
            continue
        else:
            if text[suitable[i]-1] in '1234567890':
                suitable[i] = suitable[i] - 1

    lines = [text[start:end] for start,end in zip(suitable[:-1],suitable[1:])]
    lines = lines + [text[suitable[-1]:]]
    lines = list(map(str.lstrip,list(map(str.rstrip,lines))))

    ### A conservative piece of code that checks if 
    # The first four lines have all the same number of new lines
    # The last line has more newlines than the rest
    # if yes, it separates the extra new lines and appends them as a new entry
    # this way we can strip the epilogue

    structure = [len(line.split('\n')) for line in lines]
    if len(num:=list(set(structure[:-1]))) == 1:
        if structure[0] < structure[-1]:
            mystr = lines[-1]
            mylist = mystr.split('\n')
            question5 = "\n".join(mylist[:structure[0]])
            lines[-1] = question5
            lines.append("\n".join(mylist[structure[0]:]))
    return lines  