import json
from base64 import standard_b64encode
from urllib.parse import quote

from test.common_helper import TEST_FW
from test.unit.web_interface.rest.conftest import decode_response

TEST_FW_PAYLOAD = {
    'binary': standard_b64encode(b'\x01\x23\x45\x67\x89').decode(),
    'file_name': 'no_real_file',
    'device_part': 'kernel',
    'device_name': 'no real device',
    'device_class': 'no real class',
    'version': 'no.real.version',
    'release_date': '1970-01-01',
    'vendor': 'no real vendor',
    'tags': 'tag1,tag2',
    'requested_analysis_systems': ['file_type']
}


def test_successful_request(test_app):
    response = decode_response(test_app.get('/rest/firmware'))
    assert 'error_message' not in response
    assert 'uids' in response
    assert len(response['uids']) == 1


def test_request_with_query(test_app):
    query = {'vendor': 'no real vendor'}
    quoted_query = quote(json.dumps(query))
    response = decode_response(test_app.get(f'/rest/firmware?query={quoted_query}'))
    assert 'query' in response['request'].keys()
    assert response['request']['query'] == query


def test_bad_query(test_app):
    search_query = quote('{\'vendor\': \'no real vendor\'}')
    result = decode_response(test_app.get(f'/rest/firmware?query={search_query}'))
    assert 'Query must be a json' in result['error_message']


def test_empty_response(test_app):
    response = decode_response(test_app.get('/rest/firmware?offset=1'))
    assert 'error_message' not in response
    assert len(response['uids']) == 0

    response = decode_response(test_app.get('/rest/firmware?limit=1'))
    assert 'error_message' not in response
    assert len(response['uids']) == 0


def test_bad_paging(test_app):
    response = decode_response(test_app.get('/rest/firmware?offset=X&limit=V'))
    assert 'error_message' in response
    assert 'Malformed' in response['error_message']


def test_non_existing_uid(test_app):
    result = decode_response(test_app.get('/rest/firmware/some_uid'))
    assert 'No firmware with UID some_uid' in result['error_message']


def test_successful_uid_request(test_app):
    result = decode_response(test_app.get(f'/rest/firmware/{TEST_FW.uid}'))
    assert 'firmware' in result
    assert all(section in result['firmware'] for section in ['meta_data', 'analysis'])


def test_bad_put_request(test_app):
    response = test_app.put('/rest/firmware')
    assert response.status_code == 400


def test_submit_empty_data(test_app):
    result = decode_response(test_app.put('/rest/firmware', json={}))
    assert 'Input payload validation failed' in result['message']


def test_submit_missing_item(test_app):
    request_data = {**TEST_FW_PAYLOAD}
    request_data.pop('vendor')
    result = decode_response(test_app.put('/rest/firmware', json=request_data))
    assert 'Input payload validation failed' in result['message']
    assert 'vendor' in result['errors']


def test_submit_invalid_binary(test_app):
    request_data = {**TEST_FW_PAYLOAD, 'binary': 'invalid_base64'}
    result = decode_response(test_app.put('/rest/firmware', json=request_data))
    assert 'Could not parse binary (must be valid base64!)' in result['error_message']


def test_submit_success(test_app):
    result = decode_response(test_app.put('/rest/firmware', json=TEST_FW_PAYLOAD))
    assert result['status'] == 0


def test_request_update(test_app):
    requested_analysis = json.dumps(['optional_plugin'])
    result = decode_response(test_app.put(f'/rest/firmware/{TEST_FW.uid}?update={quote(requested_analysis)}'))
    assert result['status'] == 0


def test_submit_no_tags(test_app):
    request_data = {**TEST_FW_PAYLOAD}
    request_data.pop('tags')
    result = decode_response(test_app.put('/rest/firmware', json=request_data))
    assert result['status'] == 0


def test_submit_no_release_date(test_app):
    request_data = {**TEST_FW_PAYLOAD}
    request_data.pop('release_date')
    result = decode_response(test_app.put('/rest/firmware', json=request_data))
    assert result['status'] == 0
    assert isinstance(result['request']['release_date'], str)
    assert result['request']['release_date'] == '1970-01-01'


def test_submit_invalid_release_date(test_app):
    request_data = {**TEST_FW_PAYLOAD, 'release_date': 'invalid date'}
    result = decode_response(test_app.put('/rest/firmware', json=request_data))
    assert result['status'] == 1
    assert 'Invalid date literal' in result['error_message']


def test_request_update_bad_parameter(test_app):
    result = decode_response(test_app.put(f'/rest/firmware/{TEST_FW.uid}?update=no_list'))
    assert result['status'] == 1
    assert 'has to be a list' in result['error_message']


def test_request_update_missing_parameter(test_app):  # pylint: disable=invalid-name
    result = decode_response(test_app.put(f'/rest/firmware/{TEST_FW.uid}'))
    assert result['status'] == 1
    assert 'missing parameter: update' in result['error_message']


def test_request_with_unpacking(test_app):
    scheduled_analysis = ['unpacker', 'optional_plugin']
    requested_analysis = json.dumps(scheduled_analysis)
    result = decode_response(test_app.put(f'/rest/firmware/{TEST_FW.uid}?update={quote(requested_analysis)}'))
    assert result['status'] == 0
    assert sorted(result['request']['update']) == sorted(scheduled_analysis)
    assert 'unpacker' in result['request']['update']


def test_request_with_bad_recursive_flag(test_app):  # pylint: disable=invalid-name
    result = decode_response(test_app.get('/rest/firmware?recursive=true'))
    assert result['status'] == 1
    assert 'only permissible with non-empty query' in result['error_message']

    query = json.dumps({'processed_analysis.file_type.full': {'$regex': 'arm', '$options': 'si'}})
    result = decode_response(test_app.get(f'/rest/firmware?recursive=true&query={quote(query)}'))
    assert result['status'] == 0


def test_request_with_inverted_flag(test_app):
    result = decode_response(test_app.get('/rest/firmware?inverted=true&query={"foo": "bar"}'))
    assert result['status'] == 1
    assert 'Inverted flag can only be used with recursive' in result['error_message']

    result = decode_response(test_app.get('/rest/firmware?inverted=true&recursive=true&query={"foo": "bar"}'))
    assert result['status'] == 0


def test_request_with_summary_parameter(test_app):  # pylint: disable=invalid-name
    result = decode_response(test_app.get(f'/rest/firmware/{TEST_FW.uid}?summary=true'))
    assert 'firmware' in result
