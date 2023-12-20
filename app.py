import streamlit as st
import openai
import os
import uuid
import json
from timeit import default_timer as timer
from cryptography.fernet import Fernet
import socket
import pymongo

import streamlit_antd_components as sac

from utils import send_report, clean_text, render_acceptable
from utils import generate_log, send_log

### At the beginning the app is closed and we need to show the header
#   later on, the header is shown by the update functions...

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

def reset_buttons():
    st.session_state['on_up_01'] = False
    st.session_state['on_up_02'] = False
    st.session_state['on_up_03'] = False
    st.session_state['on_up_04'] = False
    st.session_state['on_up_00'] = False

    st.session_state['on_dn_01'] = False
    st.session_state['on_dn_02'] = False
    st.session_state['on_dn_03'] = False
    st.session_state['on_dn_04'] = False
    st.session_state['on_dn_00'] = False

def is_rated():
    a0 = (st.session_state['on_up_00'] or st.session_state['on_dn_00'])
    a1 = (st.session_state['on_up_01'] or st.session_state['on_dn_01'])
    a2 = (st.session_state['on_up_02'] or st.session_state['on_dn_02'])
    a3 = (st.session_state['on_up_03'] or st.session_state['on_dn_03'])
    a4 = (st.session_state['on_up_04'] or st.session_state['on_dn_04'])
     
    return (a0 or a1 or a2 or a3 or a4)
    
       
if 'on_up_01' not in st.session_state:
    reset_buttons()


def lang_changed():
	
	if st.session_state['segmented'] == 'Italiano':
		st.session_state['lang'] = 'it'

	if st.session_state['segmented'] == 'Français':
		st.session_state['lang'] = 'fr'

	if st.session_state['segmented'] == 'English':
		st.session_state['lang'] = 'en'

	init_lang()
	init_models()
	#init_graphics()
	st.session_state['open'] = False


def init_graphics():
	st.markdown(
    """<style> div[data-testid="column"]:nth-of-type(2){ text-align: end;} </style>""", 
	unsafe_allow_html=True)

	sac.segmented([sac.SegmentedItem(label='Italiano'),
			   sac.SegmentedItem(label='Français'),
			   sac.SegmentedItem(label='English')],
			   key='segmented',
			   on_change=lang_changed,
			   format_func='title',
			   align='center',
			   size='sm',
			   radius='xs',
			   divider=False,
			   color='blue',
			   bg_color='transparent',
			   index=2)
	
	st.image('header_bg.svg', width=None, use_column_width='always')
	st.subheader(st.session_state['text_fields']['app_title'], divider='blue')
	st.write("")

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
	
	st.session_state['counter'] = 0
	st.session_state['mod'] = 3
	st.session_state['initialized'] = True
	st.session_state['jobtitle_valid'] = None
	st.session_state['query_params'] = (query_params := st.experimental_get_query_params())

	check_login()
	
	if 'id' in query_params:
		st.session_state['user_id'] = query_params['id'][0]
	else:
		st.session_state['user_id'] = None
	
	if 'lang' in query_params:
		if query_params['lang'][0] == 'it':
			st.session_state['lang'] = 'it'
		if query_params['lang'][0] == 'fr':
			st.session_state['lang'] = 'fr'
		else:
			st.session_state['lang'] = 'en'
	else:
		st.session_state['lang'] = 'en'

	init_lang()
	init_models()

	# Get the server IP and encode it
	st.session_state['server_IP'] = socket.gethostbyname(socket.gethostname())
	fernet = Fernet(os.environ["fernet_key"].encode('utf-8'))
	st.session_state['encoded_server_IP'] = fernet.encrypt(st.session_state['server_IP'].encode('utf-8'))
	
init_graphics()

def cycle():
	st.session_state['counter'] = st.session_state['counter'] + 1
	st.session_state['counter'] = st.session_state['counter'] % st.session_state['mod']

if 'open' not in st.session_state:
	st.session_state['open'] = False
	#init_graphics()
	
### Loading utility functions


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
	
	skill_cases = {'Technical Skills':"skills_technical",'Soft Skills':"skills_soft",'Mixed':"skills_mix"}

	generation_info = {}
	### make sure you replace the jobtitle.
	user_prompt = st.session_state['model']['prompt_user']
	user_prompt = user_prompt.replace("{position}",job_title)	
	user_prompt = user_prompt.replace("{skills}",st.session_state['model'][skill_cases[st.session_state['skill_types']]])
	if st.session_state['job_description'] != '':
		user_prompt = user_prompt.replace("{description}",st.session_state['model']['job_description']+st.session_state['job_description']+'\n')
	else:
		user_prompt = user_prompt.replace("{description}","")
	
	messages = [{"role": "system", "content": st.session_state['model']['prompt_system']},
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
	
	try:
		st.session_state['job_title'] = check_job_5(st.session_state['job_title'])
		if not validate_job(st.session_state['job_title'].lower()):
			st.session_state['jobtitle_valid'] = False
			st.info(f"{st.session_state['text_fields']['not_sure_if']} '{st.session_state['job_title'].capitalize()}' {st.session_state['text_fields']['is_a_job']}")
		st.session_state['jobtitle_valid'] = True
		st.session_state['client'] = load_model()
		st.session_state['generated_info'] = get_questions(st.session_state['job_title'].lower(),
													 		st.session_state['skill_types'],
													 		st.session_state['job_description'],
															st.session_state['lang'],
															st.session_state['counter'])
		
		st.session_state['generated_questions_parsed'] = clean_text(st.session_state['generated_info']['content'])
		
		end = timer()
		st.session_state['timing'] = end-start
	except ValueError as exc:
		st.session_state['generated_info'] = None
		st.session_state['generated_questions_parsed'] = [""]
		st.error(st.session_state['text_fields']['server_busy'])
		end = timer()
		st.session_state['timing'] = end-start
		log = generate_log("Error", f"The HuggingFace server gave us ValueError: {exc}", st.session_state, exception=exc.args)
		send_log(log)
		st.session_state['open'] = False
	except Exception as exc:
		st.session_state['generated_info'] = None
		st.session_state['generated_questions_parsed'] = [""]
		st.error(st.session_state['text_fields']['server_busy'])
		end = timer()
		st.session_state['timing'] = end-start
		log = generate_log("Error", f"Generic error associated with HugginsFaceHub {exc}", st.session_state, exception=exc.args)
		send_log(log)
		st.session_state['open'] = False

	#st.write(f'Sending an unrated report. It took {end-start:.1f} seconds.')
	send_report(st.session_state, rated=False)


def job_title_changed():
	reset_buttons()
	#init_graphics()
	st.session_state['job_title'] = render_acceptable(st.session_state['job_pos']).lower()
	st.session_state['counter'] = 0
	generate_after_changed_inputs()


def stars_clicked():
	reset_buttons()
	#init_graphics()
	cycle()
	generate_after_changed_inputs()


def rated(which_one):
	
    pressed = 'on_'+ which_one
    if st.session_state[pressed]:
        st.session_state[pressed] = False
    if not st.session_state[pressed]:
        st.session_state[pressed] = True
        if which_one[:2] == 'up':
            other = 'on_dn_'+which_one[-2:]
        else:
            other = 'on_up_'+which_one[-2:] 
        st.session_state[other] = False
	
    #init_graphics()
	#send_rating_log(st.session_state,rating_col) 

def to_color(state):
    if state:
        return 'primary'
    else:
        return 'secondary'  

### The visible parts of the page

with st.form('input_form'):
	st.text_input(st.session_state['text_fields']['enter_jobtitle'],
			   value='', key='job_pos', max_chars=50)
	st.selectbox(label='Nature of the questions', options=['Technical Skills','Soft Skills','Mixed'], key="skill_types")
	st.text_area(label="Job description (optional)",value="", max_chars=400, key="job_description",height=150)
	st.form_submit_button(st.session_state['text_fields']['generate_questions'],
					   on_click=job_title_changed, type='primary')
st.write("")

if st.session_state['open']:
	st.subheader(f"{st.session_state['text_fields']['questions_for']} {st.session_state['job_title'].capitalize()}:")

	for i,item in enumerate(st.session_state['generated_questions_parsed']):
		if i > 4:
			break
		with st.container():
			if st.session_state[f'on_up_{i:02d}']:
				st.success(item)
			elif st.session_state[f'on_dn_{i:02d}']:
				st.error(item)
			else:
				st.info(item)
			col1, col2 = st.columns([8,1])
			with col2:
				st.button(":thumbsup:",key=f"up_{i:02d}", on_click=rated,args=(f"up_{i:02d}",),type=to_color(st.session_state[f'on_up_{i:02d}']))
				st.button(":thumbsdown:",key=f"dn_{i:02d}", on_click=rated,args=(f"dn_{i:02d}",),type=to_color(st.session_state[f'on_dn_{i:02d}'])) 
	
	if len(st.session_state['generated_questions_parsed'])>5:
		st.info(st.session_state['generated_questions_parsed'][5])
	
	st.button(st.session_state['text_fields']['submit_regenerate'], on_click=stars_clicked, type='primary')