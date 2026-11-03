"""Local review ZIP with actual documents, tables, code and evidence bindings; no raw corpus."""
from pathlib import Path
import zipfile,hashlib,json,csv,io
import run as r
RUN=r.RUN;DOC=r.ROOT/'docs/research/fg_thesis_v1_20260908'
def main():
    assert (RUN/'FINAL_VERIFICATION.json').exists()
    destination=DOC/'DECIPROTECT_THESIS_VALIDATION_20260908_v1.zip';assert not destination.exists()
    entries={}
    def add(src,dest):
        src=Path(src);assert src.exists() and src.is_file(),src
        assert dest not in entries,dest
        assert not src.is_symlink(),src
        entries[dest]=src
    for p in DOC.iterdir():
        if p.suffix in ['.md','.txt','.csv','.png','.svg','.pdf'] and p.name not in ['THESIS_BASE_TEXT_KO.md','EVENTS_LOCAL_ONLY.csv']:
            add(p,'DOCUMENTS/'+p.name)
    add(RUN/'provenance/submission_user_designated_20260908.pdf','PAPER/submission_user_designated_20260908.pdf')
    add(RUN/'provenance/submission_user_designated_20260908.txt','PAPER/submission_extracted_text.txt')
    add(r.ROOT/'baseline/journal_final_20260905.pdf','PAPER/historical_journal_final_20260905.pdf')
    add(r.PROTOCOL,'REPRODUCIBILITY/FG_THESIS_V1_20260908.json')
    add(DOC/'THESIS_BASE_TEXT_KO.md','REPRODUCIBILITY/THESIS_BASE_TEXT_KO.md')
    for p in (RUN/'scripts').glob('*.py'):add(p,'REPRODUCIBILITY/scripts/'+p.name)
    for p in (RUN/'independent_device_preparation').iterdir():add(p,'INDEPENDENT_DEVICE_PREPARATION/'+p.name)
    for p in (RUN/'sizeprobe').iterdir():
        if p.suffix in ['.go','.mod','.sum']:add(p,'REPRODUCIBILITY/sizeprobe/'+p.name)
    for p in (r.ROOT/'research/thesis_validation_v1').rglob('*'):
        if p.is_file() and p.suffix in ['.go','.mod','.sum']:
            add(p,'SOURCE/thesis_validation_v1/'+str(p.relative_to(r.ROOT/'research/thesis_validation_v1')))
    add(RUN/'SOURCE_CHANGES.patch','SOURCE/SOURCE_CHANGES.patch')
    add(RUN/'RESERVATION_FORMAT_FIX.patch','EVIDENCE/RESERVATION_FORMAT_FIX.patch')
    for p in RUN.glob('*.json'):
        # Root records are management/aggregate artifacts, not row payloads.
        add(p,'EVIDENCE/'+p.name)
    for p in (RUN/'commands').glob('*.json'):add(p,'EVIDENCE/commands/'+p.name)
    for p in (RUN/'postprocess_log').glob('*.json'):add(p,'EVIDENCE/postprocess_log/'+p.name)
    for p in (RUN/'postprocess_attempts').glob('*'):
        if p.is_file():add(p,'EVIDENCE/postprocess_attempts/'+p.name)
    for p in (RUN/'postprocess_log').glob('*.log'):add(p,'EVIDENCE/postprocess_log/'+p.name)
    for p in (RUN/'commands').glob('*.end.json'):
        if r.read(p)['exit_code']:
            q=Path(str(p).replace('.end.json','.log'));add(q,'EVIDENCE/failure_logs/'+q.name)
    for folder in ['frozen','material_sizes','static','preflight']:
        for p in (RUN/folder).rglob('*.json'):add(p,'EVIDENCE/'+str(p.relative_to(RUN)))
    for p in (RUN/'selection').glob('*/result.json'):add(p,'EVIDENCE/selection/'+p.parent.name+'/result.json')
    for p in (RUN/'selection').glob('*/analysis.json'):add(p,'EVIDENCE/selection/'+p.parent.name+'/analysis.json')
    for p in (RUN/'selection').glob('*/concrete_*.json'):add(p,'EVIDENCE/selection/'+p.parent.name+'/'+p.name)
    for p in (RUN/'provenance/reused_evidence').iterdir():add(p,'SOURCES_REUSED/'+p.name)
    for name in ['00_CODEX_EXECUTE_KO.md','SUBMISSION_PDF_BINDING.json','REUSED_EVIDENCE_BINDINGS.json']:
        add(RUN/'provenance'/name,'SOURCES_REUSED/'+name)
    # Old sync is preserved locally; only the final small handoff is included for context.
    for name in ['PROJECT_SYNC_INDEX.md','CHATGPT_HANDOFF.md']:
        add(r.ROOT/'docs/project_sync'/name,'HANDOFF/'+name)
    manifest=[{'zip_path':dest,'original_path':str(src.resolve()),'copy_or_excerpt':'byte-identical copy',
        'bytes':src.stat().st_size,'sha256':r.sha(src)} for dest,src in sorted(entries.items())]
    buf=io.StringIO();w=csv.DictWriter(buf,manifest[0]);w.writeheader();w.writerows(manifest)
    readme='''# DeciProtect 학위 검토 자료

DOCUMENTS의 연구 상태, 실험 보고서, C′ 판단, 학위 MD/TXT 초안을 먼저 읽는다. PAPER는 사용자 지정0908 투고본과 역사적0905 PDF를 구별한다. SOURCE는 실제 격리 실행 코드와 diff, EVIDENCE는 protocol·선택 구성·실행 기록·검증 자료다. 원시 키별 결과의 실제 로컬 경로와 해시는 RAW_INDEX.csv에 있다.

이 ZIP은 문서와 증거 검수용이다. 대량 원시 전체, 예약 감사 입력·행별 출력, 모델 학습 환경, 가상환경, archive, 비밀키·토큰, 실행 바이너리를 포함하지 않는다. 원시 재집계는 기록된 로컬 경로가 있는 DeciProtect 작업 공간에서 수행한다. 기존 논문·코드·완료 결과를 덮어쓰지 않는다. 이 파일을 여는 행위는 후속 실험 실행 승인이 아니다.

MANIFEST.csv는 실제 포함 파일의 출처·바이트 수·SHA-256을 기록한다. ZIP 자체의 크기·SHA-256·재개봉 검증은 옆의 ZIP_VERIFICATION.json에 기록한다. 원격으로 자동 전송하지 않았다.
'''
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for dest,src in sorted(entries.items()):z.write(src,dest)
        z.writestr('MANIFEST.csv',buf.getvalue());z.writestr('README_KO.md',readme)
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None
        names=z.namelist();assert len(names)==len(set(names))==len(entries)+2
        for x in manifest:
            b=z.read(x['zip_path']);assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256']
        pdfhash=hashlib.sha256(z.read('PAPER/submission_user_designated_20260908.pdf')).hexdigest()
        assert pdfhash==r.read(RUN/'provenance/SUBMISSION_PDF_BINDING.json')['sha256']
        assert not any(n.startswith(('archive/','inputs/','audit/')) for n in names)
    verification={'path':str(destination.resolve()),'bytes':destination.stat().st_size,'files':len(names),
        'sha256':r.sha(destination),'zip_testzip':'PASS','all_manifest_hashes_match':True,
        'user_designated_pdf_identical':True,'raw_reserved_payload_included':False,'remote_upload':False,
        'delivery':'actual local ZIP generated and reopened; no external transfer','utc':r.now()}
    r.write(DOC/'ZIP_VERIFICATION.json',verification);print(json.dumps(verification,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
