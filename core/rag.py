"""RAG 模块：素材向量化存储与语义检索，避免将全部素材放入上下文。"""
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.materials import dedup_and_compress_materials

_ROOT = Path(__file__).resolve().parent.parent
VECTORSTORE_DIR = _ROOT / "data" / "vectorstore"

_DEFAULT_EMBED_MODEL = "BAAI/bge-small-zh-v1.5"


def get_embeddings(
    model_name: str = _DEFAULT_EMBED_MODEL,
) -> HuggingFaceEmbeddings:
    """获取 HuggingFace 嵌入模型实例。"""
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
    )


def build_vectorstore(
    materials_text: str,
    user: str,
    embeddings: HuggingFaceEmbeddings | None = None,
) -> FAISS:
    """将素材文本去重、分块、向量化并持久化到磁盘。"""
    if embeddings is None:
        embeddings = get_embeddings()

    cleaned = dedup_and_compress_materials(materials_text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n---\n\n", "\n\n", "\n", "。", "；", " "],
    )
    docs = splitter.create_documents([cleaned])

    vectorstore = FAISS.from_documents(docs, embeddings)

    store_path = VECTORSTORE_DIR / user
    store_path.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(store_path))
    print(f"[RAG] 已构建向量库：{len(docs)} 个文档块 → {store_path}")
    return vectorstore


def load_vectorstore(
    user: str,
    embeddings: HuggingFaceEmbeddings | None = None,
) -> FAISS | None:
    """从磁盘加载已有向量库，不存在则返回 None。"""
    store_path = VECTORSTORE_DIR / user
    if not (store_path / "index.faiss").exists():
        return None
    if embeddings is None:
        embeddings = get_embeddings()
    return FAISS.load_local(
        str(store_path), embeddings, allow_dangerous_deserialization=True
    )


def get_or_build_vectorstore(materials_text: str, user: str) -> FAISS:
    """优先加载已有向量库，否则构建新的。"""
    embeddings = get_embeddings()
    vs = load_vectorstore(user, embeddings)
    if vs is not None:
        print(f"[RAG] 已加载已有向量库：data/vectorstore/{user}")
        return vs
    return build_vectorstore(materials_text, user, embeddings)
