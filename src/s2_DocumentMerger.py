"""
document_merger.py
여러 개의 processed.json 파일을 하나로 통합
"""

import os
import json
from typing import Dict

class DocumentMerger:
    """여러 processed.json 파일을 하나로 통합"""
    
    def __init__(self, processed_dir: str):
        """
        Args:
            processed_dir: processed.json 파일들이 있는 디렉토리
        """
        self.processed_dir = processed_dir
        self.documents = []
    
    def load_all_documents(self):
        """모든 processed.json 파일 로드"""
        print(f"\n📂 디렉토리 스캔: {self.processed_dir}")
        
        # processed.json으로 끝나는 파일만 찾기
        json_files = [
            f for f in os.listdir(self.processed_dir) 
            if f.endswith('_processed.json')
        ]
        
        print(f"  발견된 파일: {len(json_files)}개")
        
        for i, json_file in enumerate(sorted(json_files), 1):
            file_path = os.path.join(self.processed_dir, json_file)
            
            print(f"\n  [{i}] 로딩: {json_file}")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 문서 정보 구성
                doc_info = {
                    "doc_id": f"doc_{i:03d}",  # doc_001, doc_002, ...
                    "doc_name": data["file_name"],
                    "total_pages": data["total_pages"],
                    "pages": data["pages"]
                }
                
                self.documents.append(doc_info)
                print(f"      ✓ {data['total_pages']}페이지")
                
            except Exception as e:
                print(f"      ✗ 로드 실패: {e}")
        
        print(f"\n✅ 총 {len(self.documents)}개 문서 로드 완료\n")
    
    def create_unified_structure(self) -> Dict:
        """통합 데이터 구조 생성"""
        print("🔧 통합 데이터 구조 생성 중...")
        
        unified_data = {
            "metadata": {
                "total_documents": len(self.documents),
                "documents": []
            },
            "text_blocks": []
        }
        
        block_counter = 1
        
        for doc in self.documents:
            # 문서 메타데이터 추가
            doc_meta = {
                "doc_id": doc["doc_id"],
                "doc_name": doc["doc_name"],
                "total_pages": doc["total_pages"]
            }
            unified_data["metadata"]["documents"].append(doc_meta)
            
            print(f"\n  처리 중: {doc['doc_name']}")
            
            # 각 페이지의 텍스트를 text_blocks에 추가
            for page in doc["pages"]:
                # 빈 페이지는 스킵
                if not page.get("content", "").strip():
                    continue
                
                text_block = {
                    "block_id": f"block_{block_counter:05d}",
                    "doc_id": doc["doc_id"],
                    "doc_name": doc["doc_name"],
                    "page": page["page_number"],
                    "text": page["content"]
                }
                
                unified_data["text_blocks"].append(text_block)
                block_counter += 1
            
            print(f"    ✓ {len(doc['pages'])}페이지 → {block_counter - 1}개 블록")
        
        total_blocks = len(unified_data["text_blocks"])
        print(f"\n✅ 총 {total_blocks}개 텍스트 블록 생성 완료")
        
        return unified_data
    
    def save_unified_data(self, output_path: str):
        """통합 데이터 저장"""
        unified_data = self.create_unified_structure()
        
        # 출력 디렉토리 생성
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # JSON 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(unified_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 통합 데이터 저장: {output_path}")
        print(f"  - 문서 수: {unified_data['metadata']['total_documents']}개")
        print(f"  - 텍스트 블록: {len(unified_data['text_blocks'])}개\n")

def main():
    print("="*80)
    print("📄 문서 통합 시작")
    print("="*80)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    PROCESSED_DIR = os.path.join(project_root, "data", "processed")
    OUTPUT_PATH = os.path.join(project_root, "data", "processed", "construction_law_unified.json")
    
    # 1. 디렉토리 존재 확인만
    if not os.path.exists(PROCESSED_DIR):
        print(f"\n✗ 디렉토리가 없습니다: {PROCESSED_DIR}")
        return
    
    # 2. 바로 통합 실행
    try:
        merger = DocumentMerger(PROCESSED_DIR)
        merger.load_all_documents()
        
        if not merger.documents:
            print("⚠ 처리할 문서가 없습니다.")
            return
        
        # 3. 저장 (기존 파일 자동 덮어쓰기)
        merger.save_unified_data(OUTPUT_PATH)
        
        print("✅ 문서 통합 완료!")
        
    except Exception as e:
        print(f"\n✗ 오류: {e}")

if __name__ == "__main__":
    main()