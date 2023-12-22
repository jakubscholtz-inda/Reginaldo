import streamlit as st
import uuid
from bson.binary import UuidRepresentation
import pymongo
import datetime
import os

#########################################################################################################################
### Functions associated with logging


def generate_report(session_state):

    report = {	'request_ID': session_state['request_ID'],
		   		'job_title': session_state['job_title'],
                'skill_types': session_state['skill_types'],
                'job_description': session_state['job_description'],
				'model': session_state['model'],
                'user_name':session_state['user_name'],
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
                'user_name':session_state['user_name'],
				'encoded_server_IP': session_state['encoded_server_IP'],
				'datetime': datetime.datetime.now(tz=datetime.timezone.utc),
				'generated_questions_parsed': session_state['generated_questions_parsed'],
                'timing': session_state['timing'],
                'lang': session_state['lang'],
                'type':'rating',
                'rating':{
                    'btn_thup': session_state['btn_thup'],
                    'btn_thdn': session_state['btn_thdn']
                    }
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
                'user_name':session_state['user_name'],
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
                result = collection.insert_one(generate_mini_report(session_state))
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