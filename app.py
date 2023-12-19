import streamlit as st

from langchain.llms import HuggingFaceHub
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

import openai

import random
import os
import uuid
from itertools import cycle
import json
from timeit import default_timer as timer
from cryptography.fernet import Fernet
import socket

import streamlit_antd_components as sac

from utils import send_report, clean_text, render_acceptable
from utils import generate_log, send_log
from utils import eval_rep

### At the beginning the app is closed and we need to show the header
#   later on, the header is shown by the update functions...

def lang_changed():
	
	if st.session_state['segmented'] == 'Italiano':
		st.session_state['lang'] = 'it'

	if st.session_state['segmented'] == 'Français':
		st.session_state['lang'] = 'fr'

	if st.session_state['segmented'] == 'English':
		st.session_state['lang'] = 'en'

	init_lang()
	init_models()
	init_graphics()
	st.session_state['open'] = False


def lang_clicked():
	
	if st.session_state['lang'] == 'it':
		st.session_state['lang'] = 'en'
	else:
		st.session_state['lang'] = 'it'
	init_lang()
	init_models()
	init_graphics()
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
	
if 'initialized' not in st.session_state:
	
	st.session_state['initialized'] = True
	st.session_state['jobtitle_valid'] = None
	st.session_state['query_params'] = (query_params := st.experimental_get_query_params())

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
	

if 'open' not in st.session_state:
	st.session_state['open'] = False
	st.session_state['response_stars'] = None
	st.session_state['response_text'] = None
	init_graphics()
	
### Loading utility functions


@st.cache_data(show_spinner=st.session_state['text_fields']['validation_jobtitle'],ttl=600)
def validate_job(job):
	huggingfacehub_api_token = os.environ['huggingface_token']
	llm = HuggingFaceHub(huggingfacehub_api_token=huggingfacehub_api_token,
					   repo_id=os.environ['job_checker_name'],
					   model_kwargs={"temperature":1.0, "max_new_tokens":4})
	template = st.session_state['job_question']
	prompt = PromptTemplate(template=template, input_variables=["position"])
	chain = LLMChain(prompt=prompt, llm=llm, verbose=False)
	ans = chain.run(job)
	if 'yes' in ans.lower():
		return True
	elif 'no' in ans.lower():
		return False
	else:
		return True


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
def get_questions(job_title, lang):
	"""The model name is included so that the caching does not
	depend only on the job_title."""
	
	generation_info = {}
	### make sure you replace the jobtitle.
	user_prompt = st.session_state['model']['prompt_user'].replace("{position}",job_title)
	
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
	st.session_state['open'] = True
	st.session_state['request_ID'] = uuid.uuid4()	
	st.session_state['response_stars'] = None
	st.session_state['response_text'] = None
	start = timer()
	
	#try:
	if not validate_job(st.session_state['job_title'].lower()):
		st.session_state['jobtitle_valid'] = False
		st.info(f"{st.session_state['text_fields']['not_sure_if']} '{st.session_state['job_title'].capitalize()}' {st.session_state['text_fields']['is_a_job']}")
	st.session_state['jobtitle_valid'] = True
	st.session_state['client'] = load_model()
	st.session_state['generated_info'] = get_questions(st.session_state['job_title'].lower(),
														st.session_state['lang'])
	
	st.session_state['generated_questions_parsed'] = clean_text(st.session_state['generated_info']['content'])
	
	end = timer()
	st.session_state['timing'] = end-start
	#except ValueError as exc:
	#	st.session_state['generated_info'] = None
	#	st.session_state['generated_questions_parsed'] = [""]
	#	st.error(st.session_state['text_fields']['server_busy'])
	#	end = timer()
	#	st.session_state['timing'] = end-start
	#	log = generate_log("Error", f"The HuggingFace server gave us ValueError: {exc}", st.session_state, exception=exc.args)
	#	send_log(log)
	#	st.session_state['open'] = False
	#except Exception as exc:
	#	st.session_state['generated_info'] = None
	#	st.session_state['generated_questions_parsed'] = [""]
	#	st.error(st.session_state['text_fields']['server_busy'])
	#	end = timer()
	#	st.session_state['timing'] = end-start
	#	log = generate_log("Error", f"Generic error associated with HugginsFaceHub {exc}", st.session_state, exception=exc.args)
	#	send_log(log)
	#	st.session_state['open'] = False

	#st.write(f'Sending an unrated report. It took {end-start:.1f} seconds.')
	send_report(st.session_state, rated=False)


def job_title_changed():
	init_graphics()
	st.session_state['job_title'] = render_acceptable(st.session_state['job_pos']).lower()
	generate_after_changed_inputs()


def stars_clicked():
	init_graphics()
	#st.session_state['open'] = False
	st.session_state['response_stars'] = st.session_state['rating_stars']
	st.session_state['response_text'] = st.session_state['rating_text']
	send_report(st.session_state, rated=True)
	st.toast(st.session_state['text_fields']['thanks_response'])
	generate_after_changed_inputs()


### The visible parts of the page

with st.form('input_form'):
	st.text_input(st.session_state['text_fields']['enter_jobtitle'],
			   value='', key='job_pos', max_chars=100)
	st.form_submit_button(st.session_state['text_fields']['generate_questions'],
					   on_click=job_title_changed, type='primary')
st.write("")
container =  st.container()

if st.session_state['open']:
	container.subheader(f"{st.session_state['text_fields']['questions_for']} {st.session_state['job_title'].capitalize()}:")

	for item in st.session_state['generated_questions_parsed'] :
		container.write(item)
	
	container.write("")
	container.write("")
	with container.form("eval_form", clear_on_submit=True):
		
		num_stars = st.radio(st.session_state['text_fields']['please_rate'],
						list(filter(None,eval_rep.keys())),
					key='rating_stars',
					horizontal=True,
					index=None)
		st.text_area(st.session_state['text_fields']['what_do_you_think'],
			   value=st.session_state['text_fields']['default_value'],
			   height=None, key='rating_text')
		st.form_submit_button(st.session_state['text_fields']['submit_regenerate'],
						on_click=stars_clicked, type='primary')