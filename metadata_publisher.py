import json
import requests
import logging
import time

ckan_base_url = 'http://192.168.115.56:8777'
odp_ckan_api_key = 'db3d8e4f-0299-4ae9-9637-982198cf10d0'

logging.basicConfig(level=logging.INFO)

UPDATE_METRICS = {
    'update_count':0,
    'records_added':0,
    'validated_successfully':0,
    'validation_errors': 0,
    'published':0,
    'unpublished':0,
}

#  "institution": "dea",
#  "collection": "mims-metadata",
#  "infrastructures": ["mims"],
#  "metadata_standard": "sans-1878-1",
#  "metadata": {...}

def add_a_record_to_ckan(metadat_record, institution, collection, infrastructures, metadata_standard):
    url = "{}/metadata/".format(ckan_base_url)

    print("Trying to add record into {}".format(institution))
    record_data = {
        "institution": institution,
        "collection": collection,
        "infrastructures": infrastructures, # must be a list e.g. ["mims"]
        "metadata_standard": metadata_standard,
        "metadata": metadat_record
    }

    #print(record_data)
    #print(odp_ckan_api_key)

    response = requests.post(
        url=url,
        json=record_data,
        headers={'Authorization': 'Bearer ' + odp_ckan_api_key}
    )

    #print("{}\n{}\n{}".format(url, record_data,odp_ckan_api_key))

    #print("Response on add record %r" %  (response.text))
    if response.status_code != 200:
        print("Response on add record %r" %  (response.text))
        print(record_data)
        raise RuntimeError('Request failed with return code: %s' % (
            response.status_code))
    result = json.loads(response.text)

    #print("Response keys {}".format(result.keys()))

    if check_ckan_added(institution, result):
        msg = 'Added Successfully'
        logging.info(msg)

        UPDATE_METRICS['records_added'] = UPDATE_METRICS['records_added'] + 1

    else:
        msg = 'Record not found'
        logging.info(msg)

    record_id = result['id']

    accepted_errors = []#[u'spatialRepresentationTypes', u'purpose', u'spatialResolution',
                      # u'metadataTimestamp', u'responsibleParties', u'constraints']
                       # u'lineageStatement',u'extent',u'topicCategories',u'abstract'u'relatedIdentifiers'
    errors = result['errors'].keys()
    bad_errors =[]
    for err in errors:
        if err not in accepted_errors:
            bad_errors.append(err)
    if len(bad_errors) > 0:
        #print("Bad errors {}".format(result['errors']['responsibleParties']))
        print(bad_errors)
        print(result['errors'])
        for error in bad_errors:
            print(result['metadata'][error])
        raise Exception

    record_id = result['id']
    updated = set_workflow_state('mims-published', record_id)
    UPDATE_METRICS['validated_successfully'] = UPDATE_METRICS['validated_successfully'] + 1
    if updated:
        UPDATE_METRICS['published'] = UPDATE_METRICS['published'] + 1

    """
    if result['validated'] and (len(result['errors'].keys()) == 0):#result['validate_status'] == 'success':
        msg = "Validated successfully, advancing state"
        logging.info(msg)
        updated = set_workflow_state('plone-published', record_id, organization, result)
        UPDATE_METRICS['validated_successfully'] = UPDATE_METRICS['validated_successfully'] + 1
        if updated:
            UPDATE_METRICS['published'] = UPDATE_METRICS['published'] + 1

    elif result['validated'] and (len(result['errors'].keys()) > 0):
        msg = "Validation errors:\n {}\nAttempting published state".format(result['errors'])
        logging.error(msg)
        #logging.error(result)
        updated = set_workflow_state('plone-published', record_id, organization, result)
        if updated:
            msg = "Successfully published with validation errors"
            logging.error(msg)
            UPDATE_METRICS['validated_successfully'] = UPDATE_METRICS['validated_successfully'] + 1
            UPDATE_METRICS['published'] = UPDATE_METRICS['published'] + 1
        else:
        #print(metadata_json)
            msg = "Unable to publish with validation errors, setting state to provisional"
            logging.error(msg)
            logging.error(result)
            updated = set_workflow_state('plone-provisional', record_id, organization, result)
            UPDATE_METRICS['validation_errors'] = UPDATE_METRICS['validation_errors'] + 1
            if updated:
                UPDATE_METRICS['unpublished'] = UPDATE_METRICS['unpublished'] + 1

    else:
        msg = 'Request to add record failed'
        logging.error(msg)
        logging.error(result)
    #    #print(result)
    """


    return result


def check_ckan_added(institution, result):
    time.sleep(1)
    # Find the record via jsonContent
    record_id = result['id']
    url = "{}/metadata/{}".format(
        ckan_base_url, record_id)
    try:
        response = requests.get(
            url=url,
            headers={'Authorization': 'Bearer ' + odp_ckan_api_key}
        )
    except Exception as e:
        print(e)
        return False

    if response.status_code != 200:
        return False

    found = False
    result = json.loads(response.text)
    if result['id'] == record_id:
        found = True
    return found

def set_workflow_state(state, record_id):
    data = {
        'workflow_state': state
    }

    url = "{}/metadata/workflow/{}".format(
        ckan_base_url, record_id)
    response = requests.post(
        url=url,
        params=data,
        headers={'Authorization': 'Bearer ' + odp_ckan_api_key}
    )

    result = None
    try:
        result = json.loads(response.text)
    except Exception:
        logging.error("Couldn't decode resoponse {} {}".format(response.status_code, response.text))
        raise RuntimeError('Request failed with return code: %s' % (
            response.status_code))

    print("set workflow state result {}".format(result))
    state_unchanged = False
    if response.status_code != 200 and ('message' not in result['detail']):
        raise RuntimeError('Request failed with return code: %s' % (
            response.status_code))
    if response.status_code != 200 and ('message' in result['detail']) and \
        (result['detail']['message'] != \
            'The metadata record is already assigned the specified workflow state'):
        raise RuntimeError('Request failed with return code: %s' % (
            response.status_code))
    elif response.status_code != 200 and ('message' in result['detail']) and \
        (result['detail']['message'] == \
            'The metadata record is already assigned the specified workflow state'):
        logging.info('The metadata record is already assigned the specified workflow state {}'.format(state))
        state_unchanged = True

    if not state_unchanged and result['success']:#
        msg = 'Workflow status updated to {}'.format(state)
        logging.info(msg)
        return True
    else:
        if not state_unchanged:
            msg = 'Workflow status could not be updated!\n Error {}'.format(result)
            logging.error(msg)
            return False