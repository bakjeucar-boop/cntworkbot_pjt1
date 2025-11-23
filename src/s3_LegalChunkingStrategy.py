"""
s3_LegalChunkingStrategy.py
법령 문서 청킹

메타데이터 구조:
- doc_id, doc_name, page: 문서 식별
- chunk_tokens: 토큰 수
- has_overlap: 오버랩 여부
"""

import re
import json
import os
from typing import List, Dict
import tiktoken


class LegalChunkingStrategy:
    """법령 청킹 전략"""
    
    def __init__(self, chunk_size: int = 800, overlap: int = 200, model: str = "gpt-4"):
        """
        Args:
            chunk_size: 청크 최대 토큰 수
            overlap: 청크 간 오버랩 토큰 수
            model: 토큰 계산용 모델명
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoder = tiktoken.encoding_for_model(model)

        print(f"📐 간소화 청킹 전략 초기화")        
        print(f"  - 청크 크기: {chunk_size} 토큰")
        print(f"  - 오버랩: {overlap} 토큰")
        print(f"  - 메타데이터: 최소화 (doc 정보만)")
    
    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수 계산"""
        return len(self.encoder.encode(text))
    
    def split_by_tokens(self, text: str, max_tokens: int) -> List[Dict]:
        """
        토큰 단위로 강제 분할 (최후의 수단)
        800토큰씩 잘라서 반환
        """
        tokens = self.encoder.encode(text)
        chunks = []
        
        for i in range(0, len(tokens), max_tokens):
            chunk_tokens = tokens[i:i + max_tokens]
            chunk_text = self.encoder.decode(chunk_tokens)
            chunks.append({"text": chunk_text})
        
        return chunks
    
    def split_by_article(self, text: str, max_tokens: int) -> List[Dict]:
        """
        조(條) 단위로 텍스트 분할
        
        분할 우선순위:
        1. 조(條) 단위
        2. 항(項) 단위  
        3. 토큰 제한
        """
        # 제○조 패턴으로 분할
        parts = re.split(r'(제\d+조(?:의\d+)?)', text)
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        i = 0
        while i < len(parts):
            part = parts[i].strip()
            
            if not part:
                i += 1
                continue
            
            # 제○조 패턴
            if re.match(r'제\d+조(?:의\d+)?$', part):
                article = part
                content = ""
                
                if i + 1 < len(parts):
                    content = parts[i + 1].strip()
                
                full_text = article + " " + content
                text_tokens = self.count_tokens(full_text)
                
                # 조 전체가 max_tokens 이하
                if text_tokens <= max_tokens:
                    if current_tokens + text_tokens <= max_tokens:
                        # 현재 청크에 추가
                        current_chunk += (" " if current_chunk else "") + full_text
                        current_tokens += text_tokens
                    else:
                        # 현재 청크 저장
                        if current_chunk:
                            chunks.append({"text": current_chunk})
                        # 새 청크 시작
                        current_chunk = full_text
                        current_tokens = text_tokens
                else:
                    # 조가 너무 크면 항 단위로 분할
                    if current_chunk:
                        chunks.append({"text": current_chunk})
                    
                    para_chunks = self._split_by_paragraph(article, content, max_tokens)
                    chunks.extend(para_chunks)
                    
                    current_chunk = ""
                    current_tokens = 0
                
                i += 2
            else:
                # 일반 텍스트
                part_tokens = self.count_tokens(part)
                
                if part_tokens > max_tokens:
                    # 현재 청크 저장
                    if current_chunk:
                        chunks.append({"text": current_chunk})
                    
                    # 토큰 단위로 강제 분할
                    token_chunks = self.split_by_tokens(part, max_tokens)
                    chunks.extend(token_chunks)
                    
                    # 새 청크 시작
                    current_chunk = ""
                    current_tokens = 0
                elif current_tokens + part_tokens <= max_tokens:
                    current_chunk += (" " if current_chunk else "") + part
                    current_tokens += part_tokens
                else:
                    if current_chunk:
                        chunks.append({"text": current_chunk})
                    current_chunk = part
                    current_tokens = part_tokens
                
                i += 1
        
        # 마지막 청크
        if current_chunk:
            chunks.append({"text": current_chunk})
        
        return chunks
    
    def _split_by_paragraph(self, article: str, content: str, max_tokens: int) -> List[Dict]:
        """항 단위로 분할"""
        # ①②③ 또는 1. 2. 3. 패턴으로 분할
        parts = re.split(r'([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|\d+\.)', content)
        
        chunks = []
        current_chunk = article + " "
        current_tokens = self.count_tokens(current_chunk)
        
        for part in parts:
            if not part.strip():
                continue
            
            part_tokens = self.count_tokens(part)
            
            if part_tokens > max_tokens:
                # 현재 청크 저장
                if current_chunk.strip() != article:
                    chunks.append({"text": current_chunk.strip()})
                
                # 항을 토큰 단위로 강제 분할
                token_chunks = self.split_by_tokens(article + " " + part, max_tokens)
                chunks.extend(token_chunks)
                
                # 새 청크 시작
                current_chunk = article + " "
                current_tokens = self.count_tokens(current_chunk)
            elif current_tokens + part_tokens <= max_tokens:
                current_chunk += part + " "
                current_tokens += part_tokens
            else:
                if current_chunk.strip() != article:
                    chunks.append({"text": current_chunk.strip()})
                current_chunk = article + " " + part + " "
                current_tokens = self.count_tokens(current_chunk)
        
        if current_chunk.strip() != article:
            chunks.append({"text": current_chunk.strip()})
        
        return chunks
    
    def process_from_unified_json(self, json_path: str) -> List[Dict]:
        """
        통합 JSON에서 청킹 수행
        
        Returns:
            청크 리스트 with 간소화된 메타데이터
        """
        print(f"\n📖 JSON 로드: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        text_blocks = data.get('text_blocks', [])
        print(f"✓ {len(text_blocks)}개 텍스트 블록")
        
        all_chunks = []
        chunk_counter = 1
        
        print(f"\n🔪 청킹 시작...")
        
        for idx, block in enumerate(text_blocks, 1):
            text = block['text']
            
            # 구조 인식 청킹
            text_chunks = self.split_by_article(text, self.chunk_size)
            
            for chunk_data in text_chunks:
                chunk_text = chunk_data["text"]
                
                # 간소화된 메타데이터
                chunk = {
                    "chunk_id": f"chunk_{chunk_counter:05d}",
                    "content": chunk_text,
                    "metadata": {
                        "doc_id": block["doc_id"],
                        "doc_name": block["doc_name"],
                        "page": block.get("page", 0),
                        "chunk_tokens": self.count_tokens(chunk_text)
                    }
                }
                all_chunks.append(chunk)
                chunk_counter += 1
            
            if idx % 50 == 0:
                print(f"  진행: {idx}/{len(text_blocks)} 블록...")
        
        # 오버랩 적용
        print(f"\n🔗 오버랩 적용...")
        final_chunks = self.apply_overlap(all_chunks)
        
        print(f"✅ 최종 {len(final_chunks)}개 청크\n")
        
        return final_chunks
    
    def apply_overlap(self, chunks: List[Dict]) -> List[Dict]:
        """청크 간 오버랩 적용"""
        if not chunks or self.overlap == 0:
            return chunks
        
        overlapped_chunks = []
        
        for i, chunk in enumerate(chunks):
            content = chunk["content"]
            
            # 다음 청크가 있고, 같은 문서인 경우
            if i < len(chunks) - 1:
                next_chunk = chunks[i + 1]
                
                if next_chunk["metadata"]["doc_id"] == chunk["metadata"]["doc_id"]:
                    next_content = next_chunk["content"]
                    
                    # 오버랩 토큰 추출
                    tokens = self.encoder.encode(next_content)
                    if len(tokens) > self.overlap:
                        overlap_tokens = tokens[:self.overlap]
                        overlap_text = self.encoder.decode(overlap_tokens)
                        content += f"\n\n[다음 내용 미리보기]\n{overlap_text}..."
            
            # 오버랩 적용된 청크
            overlapped_chunks.append({
                **chunk,
                "content": content,
                "metadata": {
                    **chunk["metadata"],
                    "has_overlap": i < len(chunks) - 1,
                    "chunk_tokens": self.count_tokens(content)
                }
            })
        
        return overlapped_chunks
    
    def save_chunks(self, chunks: List[Dict], output_path: str):
        """청크를 JSON 파일로 저장"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        
        print(f"💾 청크 저장: {output_path}")
        print(f"  - 청크 수: {len(chunks)}개")


def main():
    """실행 메인 함수"""
    print("="*80)
    print("🔪 간소화 법령 청킹")
    print("="*80)
    
    # 경로 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    INPUT_PATH = os.path.join(project_root, "data", "processed", "construction_law_unified.json")
    OUTPUT_PATH = os.path.join(project_root, "data", "chunks", "construction_law_chunks.json")
    
    print(f"\n입력: {INPUT_PATH}")
    print(f"출력: {OUTPUT_PATH}")
    
    if not os.path.exists(INPUT_PATH):
        print(f"\n✗ 입력 파일 없음: {INPUT_PATH}")
        return
    
    if os.path.exists(OUTPUT_PATH):
        response = input(f"\n⚠ 파일 존재. 덮어쓰기? (y/n): ")
        if response.lower() != 'y':
            print("취소")
            return
    
    try:
        chunker = LegalChunkingStrategy(
            chunk_size=800,
            overlap=200,
            model="gpt-4"
        )
        
        chunks = chunker.process_from_unified_json(INPUT_PATH)
        chunker.save_chunks(chunks, OUTPUT_PATH)
        
        print("="*80)
        print("✅ 청킹 완료!")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()