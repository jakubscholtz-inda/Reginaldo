import streamlit as st
import os
import pymongo
from bson.binary import UuidRepresentation
import datetime


def acceptable_input(input):
	return all((x.isalnum() or x.isspace() or x == '_' or x == '-') for x in input)


def render_acceptable(input):
	return "".join([x for x in input if (x.isalnum() or x.isspace() or x == '_' or x == '-')])


def clean_text(text):
    text = text.rstrip().lstrip().replace('#','')
    indices = [i for i, chr in enumerate(text) if chr in '123456789']
    if len(indices) == 0:
         return [""]
    lines = [text[start:end] for start,end in zip(indices[:-1],indices[1:])]
    lines = lines + [text[indices[-1]:]]
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

        
	

def generate_report(session_state):

    report = {	'request_ID': session_state['request_ID'],
		   		'job_title': session_state['job_title'],
                'skill_types': session_state['skill_types'],
                'job_description': session_state['job_description'],
				'model': session_state['model'],
				'user_id': session_state['user_id'],
				'encoded_server_IP': session_state['encoded_server_IP'],
				'datetime': datetime.datetime.now(tz=datetime.timezone.utc),
				'generated_info': session_state['generated_info'],
                'generated_questions_parsed': session_state['generated_questions_parsed'],
                'timing': session_state['timing'],
                'query_params': session_state['query_params'],
                'jobtitle_valid': session_state['jobtitle_valid'],
                'lang': session_state['lang'],
                'type':'report'}
    
    return report

def generate_mini_report(session_state):

    report = {	'request_ID': session_state['request_ID'],
		   		'job_title': session_state['job_title'],
                'skill_types': session_state['skill_types'],
                'job_description': session_state['job_description'],
				'model': session_state['model'],
				'user_id': session_state['user_id'],
				'encoded_server_IP': session_state['encoded_server_IP'],
				'datetime': datetime.datetime.now(tz=datetime.timezone.utc),
				'generated_questions_parsed': session_state['generated_questions_parsed'],
                'timing': session_state['timing'],
                'lang': session_state['lang'],
                'type':'rating',
    
                'on_up_01': session_state['on_up_01'],
                'on_up_02': session_state['on_up_02'],
                'on_up_03': session_state['on_up_03'],
                'on_up_04': session_state['on_up_04'],
                'on_up_05': session_state['on_up_00'],

                'on_dn_01': session_state['on_dn_01'],
                'on_dn_01': session_state['on_dn_02'],
                'on_dn_01': session_state['on_dn_03'],
                'on_dn_01': session_state['on_dn_04'],
                'on_dn_01': session_state['on_dn_00']
    }
    return report


def generate_log(level, message, session_state,**kwargs):
    log = {
          'level':level,
          'type':'log',
          'message':message,
          'datetime': datetime.datetime.now(tz=datetime.timezone.utc),
          'data': kwargs,
          'session_state':{
                'request_ID': session_state['request_ID'],
		   		'job_title': session_state['job_title'],
                'skill_types': session_state['skill_types'],
                'job_description': session_state['job_description'],
				'model': session_state['model'],
				'user_id': session_state['user_id'],
				'encoded_server_IP': session_state['encoded_server_IP'],
				'generated_info': session_state['generated_info'],
                'query_params': session_state['query_params'],
                'jobtitle_valid': session_state['jobtitle_valid'],
                'timing': session_state['timing'],
                'lang': session_state['lang']}
          }

    return log


def send_report(session_state, rated):

    try:
        with pymongo.MongoClient(os.environ['mongo_login_reg'], uuidRepresentation='standard') as mongoclient:
            if rated:
                collection = mongoclient[os.environ['mongo_db']][os.environ['mongo_col_rated']]
            else:
                collection = mongoclient[os.environ['mongo_db']][os.environ['mongo_col_unrated']]
            
            result = collection.insert_one(generate_report(session_state))

            if result.inserted_id:
                return str(result.inserted_id)
            else:
                st.toast("Cannot save the report!",icon=':volcano:')
    except pymongo.errors.PyMongoError as e:
        st.toast("Cannot save the report!",icon=':volcano:')
        ## Without mongo we cannot actually send a log...
         

def send_log(log):

    try:
        with pymongo.MongoClient(os.environ['mongo_login_reg'], uuidRepresentation='standard') as mongoclient:
            collection = mongoclient[os.environ['mongo_db']][os.environ['mongo_col_logging']]
            
            result = collection.insert_one(log)

            if result.inserted_id:
                return str(result.inserted_id)
            else:
                st.toast("Cannot save the log!",icon=':volcano:')
    except pymongo.errors.PyMongoError as e:
        st.toast("Cannot save the log!",icon=':volcano:')
        ## Without mongo we cannot actually send a log...

