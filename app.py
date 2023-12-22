import streamlit as st
import streamlit_antd_components as sac
import openai
import os
import uuid
from timeit import default_timer as timer
from cryptography.fernet import Fernet
import pymongo
import socket

import json

from utils_logging import send_report, generate_log, send_log 
from utils import clean_text, render_acceptable, url_detector, url_2_text
from utils import init_lang, init_models, to_color, get_and_store_serverIP, cycle
from utils import not_blank_rating, reset_buttons

lang_2_index = {'it': 1, 'en': 0, 'fr': 2}
lang_2_twoletter = { 'Italiano':'it', 'Français':'fr', 'English':'en'}

skill_options = {
	'en':['Technical/Hard Skills','Soft Skills','Mixed'],
 	'it':['Competenze Tecniche [Hard skills]','Competenze Trasversali [Soft Skills]','Entrambi'],
 	'fr':['Compétences Techniques [Hard Skills]','Compétences Non Techniques [Soft Skills]','Tous Les Deux']
 		}

skill_cases = {}
for key,lang_set in skill_options.items():
	for key,val in zip(lang_set,["skills_technical","skills_soft","skills_mix"]):
		skill_cases[key] = val

def lang_changed():
	st.session_state['lang'] = lang_2_twoletter[st.session_state['segmented']]
	init_lang()
	init_models()
	st.session_state['open'] = False


def check_login():
    st.session_state['query_params'] = st.experimental_get_query_params()

    if 'user' in st.session_state['query_params']:
        with pymongo.MongoClient(os.environ['mongo_login_reg'], uuidRepresentation='standard') as mongoclient:
            collection = mongoclient[os.environ['mongo_db']][os.environ['mongo_col_users']]
            result = collection.find_one({'user_token': st.session_state['query_params']['user'][0]})
        if result is not None:
            st.toast(f"Welcome {result['user_name']}!")
            st.session_state['user_name'] = result['user_name']
            st.session_state['unlocked'] = True
        else:
            st.session_state['user_name'] = 'Failed Login'
            st.session_state['unlocked'] = False
            ### It does not make sense to make this text multilingual, because it all happens before the user has a chance to change the language
            ### Unless we make the language changeable by outside source.
            st.error("Invalid user, I will not be able to connect to the LLM server.\nPlease reach out to Intervieweb for login information.")            
    else:
        if socket.gethostbyname(socket.gethostname()) == '127.0.1.1':
            st.toast(f"Local use?")
            st.session_state['unlocked'] = True
            st.session_state['user_name'] = 'Local'
        else:
            st.session_state['unlocked'] = False
            st.session_state['user_name'] = 'Failed Login'
            ### It does not make sense to make this text multilingual, because it all happens before the user has a chance to change the language
            ### Unless we make the language changeable by outside source.
            st.error("Invalid user, I will not be able to connect to the LLM server.\nPlease reach out to Intervieweb for login information.")

if 'initialized' not in st.session_state:
	# This block initializes the state
	st.session_state['initialized'] = True
	reset_buttons()
	st.session_state['open'] = False
	st.session_state['counter'] = 0
	st.session_state['mod'] = 3
	st.session_state['jobtitle_valid'] = None
	st.session_state['query_params'] = (query_params := st.experimental_get_query_params())

	if 'lang' in query_params:
		if query_params['lang'][0] in list(lang_2_index.keys()):
			st.session_state['lang'] == query_params['lang'][0]
		else:
			st.session_state['lang'] = 'en'
	else:
		st.session_state['lang'] = 'en'

	init_lang()
	check_login()
	init_models()
	get_and_store_serverIP()
	

@st.cache_data(show_spinner=st.session_state['text_fields']['validation_jobtitle'],ttl=600)
def validate_job(job):
	return True

def check_job_5(job):
	pieces = job.split(' ')
	return " ".join(pieces[:5])

@st.cache_resource(ttl=3600)
def load_model():
    try:
        client =  openai.OpenAI(api_key=os.environ['openai_api_key'])
        return client
    except openai.error.Timeout as exc:
        #Handle timeout error, e.g. retry or log
        send_log("Error", f"OpenAI API request timed out: {exc}", st.session_state,exception=exc.args)
        st.error("We are sorry, we are unable to connect to the language model server. Please try later.")
        return None
    except openai.error.APIError as exc:
        #Handle API error, e.g. retry or log
        send_log("Error", f"OpenAI API returned an API Error: {exc}", st.session_state,exception=exc.args)
        st.error("We are sorry, we are unable to connect to the language model server. Please try later.")
        return None        
    except openai.error.APIConnectionError as exc:
        #Handle connection error, e.g. check network or log
        send_log("Error", f"OpenAI API request failed to connect: {exc}", st.session_state,exception=exc.args)
        st.error("We are sorry, we are unable to connect to the language model server. Please try later.")
        return None 
    except openai.error.InvalidRequestError as exc:
        #Handle invalid request error, e.g. validate parameters or log
        send_log("Error", f"OpenAI API request was invalid: {exc}", st.session_state,exception=exc.args)
        st.error("We are sorry, we are unable to connect to the language model server. Please try later.")
        return None 
    except openai.error.AuthenticationError as exc:
        #Handle authentication error, e.g. check credentials or log
        send_log("Error", f"OpenAI API request was not authorized: {exc}", st.session_state,exception=exc.args)
        st.error("We are sorry, we are unable to connect to the language model server. Please try later.")
        return None 
    except openai.error.PermissionError as exc:
        #Handle permission error, e.g. check scope or log
        send_log("Error", f"OpenAI API request was not permitted: {exc}", st.session_state,exception=exc.args)
        st.error("We are sorry, we are unable to connect to the language model server. Please try later.")
        return None 
    except openai.error.RateLimitError as exc:
        #Handle rate limit error, e.g. wait or log
        send_log("Error", f"OpenAI API request exceeded rate limit: {exc}", st.session_state,exception=exc.args)
        st.error("We are sorry, we are unable to connect to the language model server. Please try later.")
        return None


@st.cache_data(show_spinner=st.session_state['text_fields']['generation_questions'],ttl=600)
def get_questions(job_title, skills, description, lang, counter):
	"""The model name is included so that the caching does not
	depend only on the job_title."""

	generation_info = {}
	### make sure you replace the jobtitle.
	user_prompt = st.session_state['model']['prompt_user']
	system_prompt = st.session_state['model']['prompt_system']

	user_prompt = user_prompt.replace("{position}",job_title)	
	
	if st.session_state['job_description'] != '':
		prepared = st.session_state['model']['job_description'].replace("{details}",description)
		user_prompt = user_prompt.replace("{description}",prepared)
	else:
		user_prompt = user_prompt.replace("{description}","")
	
	system_prompt = system_prompt.replace("{skills}","")
	user_prompt = user_prompt.replace("{skills}",st.session_state['model'][skill_cases[st.session_state['skill_types']]])
	
	messages = [{"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt}]
	
	generation_info['messages'] = messages
	generation_info['params'] = st.session_state['model']['params']
	openai_answer = st.session_state['client'].chat.completions.create(messages=messages, **st.session_state['model']['params'])

	generation_info['id'] = openai_answer.id
	generation_info['model'] = openai_answer.model
	generation_info['prompt_tokens'] = openai_answer.usage.prompt_tokens
	generation_info['completion_tokens'] = openai_answer.usage.completion_tokens
	generation_info['content'] = openai_answer.choices[0].message.content
	generation_info['system_fingerprint'] = openai_answer.system_fingerprint
	return generation_info


def generate_after_changed_inputs():
	"""Note that both load_model and get_questions are cached, they can be quick."""
	reset_buttons()
	st.session_state['open'] = True
	st.session_state['request_ID'] = uuid.uuid4()	
	start = timer()
	
	st.session_state['job_title'] = check_job_5(st.session_state['job_title'])
	if not validate_job(st.session_state['job_title'].lower()):
		st.session_state['jobtitle_valid'] = False
	else:
		st.session_state['jobtitle_valid'] = True
		
	if not st.session_state['unlocked']:
		st.error("Please use the correct login token")
		st.session_state['generated_info'] = None
		st.session_state['generated_questions_parsed'] = ''
	### If unlocked and happy
	else:

		### Check if the description is a url, if it is, use it.
		description_url=url_detector(st.session_state['job_description'])
		if description_url is None:
			description = st.session_state['job_description']
		else:
			description = url_2_text(description_url)
			if description is None:
				description = st.session_state['job_description']
			else:
				headers = description[0]
				cont = description[1]
				new_descr = '"""' + headers[0] + '\n' + cont[0] + '\n'
				new_descr += headers[1] + '\n' + cont[1] + '"""'
				description = new_descr
						
		try:
			st.session_state['client'] = load_model()
			
			st.session_state['generated_info'] = get_questions(st.session_state['job_title'].lower(),
															st.session_state['skill_types'],
															description,
															st.session_state['lang'],
															st.session_state['counter'])
		
			st.session_state['generated_questions_parsed'] = clean_text(st.session_state['generated_info']['content'])

			end = timer()
			st.session_state['timing'] = end-start
		
		except Exception as exc:
			st.session_state['generated_info'] = None
			st.session_state['generated_questions_parsed'] = [""]
			st.error(st.session_state['text_fields']['server_busy'])
			end = timer()
			st.session_state['timing'] = end-start
			log = generate_log("Error", f"Generic error {exc}", st.session_state, exception=exc.args)
			send_log(log)
			st.session_state['open'] = False

	send_report(st.session_state, rated=False)


def job_title_changed():
	reset_buttons()
	st.session_state['job_title'] = render_acceptable(st.session_state['job_pos']).lower()
	st.session_state['counter'] = 0
	generate_after_changed_inputs()


def regenerate_clicked():
	reset_buttons()
	cycle()
	generate_after_changed_inputs()


def rated(clicked,index):
	"""Button logic"""
	if not st.session_state[clicked][index]:
		if clicked == 'btn_thup':
			other = 'btn_thdn'
		else:
			other = 'btn_thup'
		st.session_state[clicked][index] = True
		st.session_state[other][index] = False
		send_report(st.session_state, rated=True)
	  

### The visible parts of the page

st.markdown("""
            <style>
                div[data-testid="column"]:nth-of-type(2) {
                    width: fit-content !important;
                    flex: unset;
                    position: absolute;
                    bottom: 0px;
                    right: 8px;  
                }
                div[data-testid="column"]:nth-of-type(2) div[data-testid="stVerticalBlock"] {
                    flex-direction: row-reverse;
                    gap: 4px;
                    transform: scale(.8);
                    transform-origin: 100%;
                }
                div[data-testid="column"]:nth-of-type(2) * {
                    width: fit-content !important;
                    flex: unset;
                }
            @media (max-width: 640px) {
                div[data-testid="column"]:nth-of-type(2) {
                    min-width: calc(100% - 1.5rem);
                    position: relative !important;
                    top: unset !important;
                    right: unset !important;
                }
            }
            </style>
            """, unsafe_allow_html=True)

st.markdown("""<style> div[data-testid="column"]:nth-of-type(2){ text-align: end;} </style>""",unsafe_allow_html=True)

sac.segmented([sac.SegmentedItem(label='English'),
			sac.SegmentedItem(label='Italiano'),
			sac.SegmentedItem(label='Français')],
			key='segmented',
			on_change=lang_changed,
			format_func='title',
			align='center',
			size='sm',
			radius='xs',
			divider=False,
			color='blue',
			bg_color='transparent',
			index=lang_2_index[st.session_state['lang']])

st.image('header_bg.svg', width=None, use_column_width='always')
st.subheader(st.session_state['text_fields']['app_title'], divider='blue')
st.write("")

with st.form('input_form'):
	st.text_input(st.session_state['text_fields']['enter_jobtitle'],
			   value='', key='job_pos', max_chars=50)
	st.selectbox(label=st.session_state['text_fields']['nature_questions'],
			  options=skill_options[st.session_state['lang']],
			  key="skill_types")
	st.text_area(label=st.session_state['text_fields']['job_description'],
			  value="",
			  max_chars=2000,  # about 500 tokens?
			  key="job_description",
			  height=150)
	st.form_submit_button(st.session_state['text_fields']['generate_questions'],
					   on_click=job_title_changed, type='primary')
st.write("")

if st.session_state['open']:
	st.subheader(f"{st.session_state['text_fields']['questions_for']} {st.session_state['job_title'].capitalize()}:")

	for i,item in enumerate(st.session_state['generated_questions_parsed']):
		if i > 9:
			break
		with st.container():
			if st.session_state['btn_thup'][i]:
				st.success(item)
			elif st.session_state['btn_thdn'][i]:
				st.error(item)
			else:
				st.info(item)
			col1, col2 = st.columns([8,1])
			with col2:
				st.button(":thumbsup:",  key=f"up_{i:02d}", on_click=rated, args=(f"btn_thup",i,),type=to_color(st.session_state['btn_thup'][i]))
				st.button(":thumbsdown:",key=f"dn_{i:02d}", on_click=rated, args=(f"btn_thdn",i,),type=to_color(st.session_state['btn_thdn'][i])) 
	
	if len(st.session_state['generated_questions_parsed'])>10:
		st.info(st.session_state['generated_questions_parsed'][5])
	
	st.button(st.session_state['text_fields']['submit_regenerate'], on_click=regenerate_clicked, type='primary')