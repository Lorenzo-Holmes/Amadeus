"""Authored neutral Responses fixtures. No historical/private/heldout content."""
from __future__ import annotations
import copy
import json

REASONING = 'PRIVATE_AUTHORED_REASONING_MUST_NEVER_BECOME_A_REPLY'
VISIBLE = 'The invented blue marker is beside the empty notebook.'
KINDS = ('completed_text','reasoning_only','empty_message','incomplete','failed',
         'disconnect','malformed_sequence','tokens_without_reasoning_text','bad_usage')

def events(kind):
    if kind not in KINDS:raise ValueError('Unknown authored fixture')
    identity={'id':'resp_authored_terminal','object':'response','model':'deepseek-v4-pro'}
    result=[]
    def add(name,**fields):
        result.append({'type':name,'sequence_number':len(result),**copy.deepcopy(fields)})
    add('response.created',response={**identity,'status':'in_progress','output':[]})
    add('response.in_progress',response={**identity,'status':'in_progress','output':[]})
    output=[]
    if kind!='tokens_without_reasoning_text':
        item={'id':'rs_authored','type':'reasoning','status':'in_progress','content':[],'summary':[]}
        add('response.output_item.added',output_index=0,item=item)
        add('response.content_part.added',item_id=item['id'],output_index=0,content_index=0,part={'type':'reasoning_text','text':''})
        for delta in (REASONING[:17],REASONING[17:]):
            add('response.reasoning_text.delta',item_id=item['id'],output_index=0,content_index=0,delta=delta)
        add('response.reasoning_text.done',item_id=item['id'],output_index=0,content_index=0,text=REASONING)
        part={'type':'reasoning_text','text':REASONING}
        add('response.content_part.done',item_id=item['id'],output_index=0,content_index=0,part=part)
        item.update(status='completed',content=[part])
        add('response.output_item.done',output_index=0,item=item);output.append(item)
    if kind!='reasoning_only' and kind!='failed':
        index=len(output);text='' if kind=='empty_message' else VISIBLE
        item={'id':'msg_authored','type':'message','role':'assistant','status':'in_progress','content':[]}
        add('response.output_item.added',output_index=index,item=item)
        add('response.content_part.added',item_id=item['id'],output_index=index,content_index=0,part={'type':'output_text','text':'','annotations':[]})
        if text:add('response.output_text.delta',item_id=item['id'],output_index=index,content_index=0,delta=text)
        add('response.output_text.done',item_id=item['id'],output_index=index,content_index=0,text=text)
        part={'type':'output_text','text':text,'annotations':[]}
        add('response.content_part.done',item_id=item['id'],output_index=index,content_index=0,part=part)
        item.update(status='completed',content=[part]);output.append(item)
        add('response.output_item.done',output_index=index,item=item)
    status=kind if kind in ('incomplete','failed') else 'completed'
    usage={'input_tokens':100,'input_tokens_details':{'cached_tokens':10},'output_tokens':20,
           'output_tokens_details':{'reasoning_tokens':20 if kind=='reasoning_only' else 12},'total_tokens':120}
    if kind=='bad_usage':usage['total_tokens']=121
    response={**identity,'status':status,'output':output,'usage':usage,
              'error':{'code':'authored_failure','message':'Synthetic failure.'} if kind=='failed' else None,
              'incomplete_details':{'reason':'max_output_tokens'} if kind=='incomplete' else None}
    if kind!='disconnect':add('response.'+status,response=response)
    if kind=='malformed_sequence':result[2]['sequence_number']=0
    return result

def wire(kind):
    return encode_events(events(kind))

def encode_events(values):
    return b''.join(('event: '+e['type']+'\ndata: '+json.dumps(e,ensure_ascii=False,separators=(',',':'))+'\n\n').encode() for e in values)
