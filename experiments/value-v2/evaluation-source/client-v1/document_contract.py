"""Document subject binding and reviewable report validation."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat


class EvidenceError(ValueError):
    pass


def read_regular(path, limit):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise EvidenceError('Index must be a regular file')
        raw=handle.read(limit+1)
    if len(raw)>limit:
        raise EvidenceError('Document index is too large')
    return raw


class SubjectScope:
    def __init__(self,root,doc_ids,task,subject=None):
        self.index={}
        self.subjects=[]
        self.receipt={'mode':'unscoped','subjects':[]}
        path=Path(root)/'document-index.json'
        if not path.exists() and not path.is_symlink():
            if subject:
                raise EvidenceError('A subject requires document-index.json')
            return
        raw=read_regular(path,131072)
        def pairs(items):
            result={}
            for key,value in items:
                if key in result:raise EvidenceError('Duplicate index key')
                result[key]=value
            return result
        index=json.loads(raw,object_pairs_hook=pairs)
        if set(index)!={'version','subjects','documents'} or index['version']!=1:
            raise EvidenceError('Unsupported document index')
        subjects=index['subjects'];documents=index['documents']
        if not isinstance(subjects,dict) or not 1<=len(subjects)<=256 or not isinstance(documents,dict):
            raise EvidenceError('Invalid index maps')
        if set(documents)!=set(doc_ids):
            raise EvidenceError('Index must cover exactly the available documents')
        aliases={}
        for key,names in subjects.items():
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',key) or not isinstance(names,list) or not 1<=len(names)<=8:
                raise EvidenceError('Invalid subject or aliases')
            for name in [key]+names:
                if not isinstance(name,str) or not 1<=len(name)<=120:
                    raise EvidenceError('Invalid subject alias')
                folded=name.casefold()
                if folded in aliases and aliases[folded]!=key:
                    raise EvidenceError('Subject alias is ambiguous')
                aliases[folded]=key
        for doc_id,meta in documents.items():
            if not isinstance(meta,dict) or set(meta)!={'subject','sha256'}:
                raise EvidenceError('Invalid document metadata')
            if meta['subject'] not in subjects or not re.fullmatch(r'[a-f0-9]{64}',meta['sha256']):
                raise EvidenceError('Invalid document subject or digest')
        self.index=documents
        self.aliases=aliases
        detected=self.identify(task)
        if subject is not None:
            requested=[subject] if isinstance(subject,str) else list(subject)
            if not requested or set(requested)-subjects.keys():
                raise EvidenceError('Unknown requested subject')
            if detected-set(requested):
                raise EvidenceError('Task names a subject outside the selected scope')
            self.subjects=sorted(set(requested));mode='explicit'
        else:
            if not detected:
                raise EvidenceError('Name a subject from the document index or pass --subject')
            self.subjects=sorted(detected);mode='inferred_from_registered_alias'
        self.receipt={'mode':mode,'subjects':self.subjects,
                      'index_sha256':hashlib.sha256(raw).hexdigest()}

    def identify(self,text):
        found=[]
        folded=text.casefold()
        for alias,key in sorted(self.aliases.items(),key=lambda pair:-len(pair[0])):
            for match in re.finditer(re.escape(alias),folded):
                start,end=match.span()
                # ASCII identifiers must not match prefixes of another project.
                if start and re.match(r'[a-z0-9_.-]',folded[start-1]):continue
                if end<len(folded) and re.match(r'[a-z0-9_.-]',folded[end]):continue
                if any(start>=a and end<=b for a,b,_ in found):continue
                found.append((start,end,key))
        return {key for _,_,key in found}

    def allows(self,doc_id):
        return not self.index or self.index[doc_id]['subject'] in self.subjects

    def verify(self,document):
        if self.index:
            meta=self.index[document['doc_id']]
            if meta['subject'] not in self.subjects:
                raise EvidenceError('Document is outside the task subject scope')
            if meta['sha256']!=document['sha256']:
                raise EvidenceError('Document content differs from the indexed digest')


def validate_report(report,read_documents):
    citations=report['citations']
    if len(citations)!=len(set(citations)):
        raise EvidenceError('Duplicate citations')
    if set(citations)-read_documents.keys():
        raise EvidenceError('Report cites a document that was not read')
    if report['status']=='answered' and not citations:
        raise EvidenceError('A factual report requires a read document citation')
    answer=report['answer'].strip()
    tail=answer.rstrip('\"\u201d\u2019)]}')
    if not tail.endswith(('.', '!', '?', '\u3002', '\uff01', '\uff1f')):
        raise EvidenceError('Answer appears unfinished. Rewrite a shorter complete answer ending with punctuation')
    stack=[];closing={')':'(',']':'[','}':'{','\u201d':'\u201c','\u2019':'\u2018'}
    for char in answer:
        if char in closing.values():stack.append(char)
        elif char in closing:
            if not stack or stack.pop()!=closing[char]:
                raise EvidenceError('Answer has unmatched brackets or quotes')
    if stack or answer.count('"')%2 or answer.count('```')%2:
        raise EvidenceError('Answer has unmatched brackets or quotes')
    supported=set()
    for evidence in report['evidence']:
        doc_id=evidence['doc_id'];quote=evidence['quote']
        if doc_id not in read_documents or doc_id not in citations:
            raise EvidenceError('Evidence must come from a read and cited document')
        if not quote.strip() or quote not in read_documents[doc_id]['text']:
            raise EvidenceError('Evidence quote is not an exact passage from the read document')
        supported.add(doc_id)
    if supported!=set(citations):
        raise EvidenceError('Every citation requires an exact evidence quote')
