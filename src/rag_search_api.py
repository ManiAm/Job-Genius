
import getpass
import requests

from rest_client import REST_API_Client


class RAG_SEARCH_REST_API_Client(REST_API_Client):

    def __init__(self,
                 url,
                 api_ver=None,
                 base=None,
                 user=getpass.getuser()):

        super().__init__(url, api_ver, base, user)


    def is_healthy(self):

        url = f"{self.baseurl}/health"

        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"RAG-Talk health check failed: {e}")
            return False

    #######################################

    def get_llm_models(self):

        url = f"{self.baseurl}/api/v1/llm/models"

        return self.request("GET", url, timeout=10)


    def get_llm_info(self, model_name):

        url = f"{self.baseurl}/api/v1/llm/model-info"

        params = {
            "model_name": model_name
        }

        return self.request("GET", url, params=params, timeout=10)


    def llm_chat(self, question, llm_model, context="", session_id="default", timeout=1*60):

        url = f"{self.baseurl}/api/v1/llm/chat"

        payload = {
            "question": question,
            "llm_model": llm_model,
            "context": context,
            "session_id": session_id
        }

        return self.request("POST", url, json=payload, timeout=timeout)


    #######################################

    def load_model(self, model_list, timeout=5*60):

        url = f"{self.baseurl}/api/v1/rag/load-model"

        json = {
            "models": model_list
        }

        return self.request("POST", url, params=json, timeout=timeout)


    def unload_model(self, model_name):

        url = f"{self.baseurl}/api/v1/rag/unload-model/{model_name}"

        return self.request("DELETE", url)


    def unload_all_models(self):

        url = f"{self.baseurl}/api/v1/rag/unload-all-models"

        return self.request("DELETE", url)


    def get_max_tokens(self, embed_model):

        url = f"{self.baseurl}/api/v1/rag/max-tokens"

        status, output = self.request("GET", url)
        if not status:
            return False, output

        max_tokens = output.get(embed_model, None)
        if not max_tokens:
            return False, f"Cannot find max tokens of embedding model {embed_model}"

        return True, max_tokens


    ##########

    def rag_chat(
        self,
        question,
        llm_model,
        embed_model,
        collection_name,
        instructions="",
        session_id="default",
        score_threshold=0.7,
        max_documents=5,
        timeout=1*60):

        url = f"{self.baseurl}/api/v1/rag/chat"

        payload = {
            "question": question,
            "llm_model": llm_model,
            "embed_model": embed_model,
            "collection_name": collection_name,
            "instructions": instructions,
            "session_id": session_id,
            "score_threshold": score_threshold,
            "max_documents": max_documents
        }

        return self.request("POST", url, json=payload, timeout=timeout)

    ##########

    def split_document(self, text, chunk_size=1000, separators=None):

        url = f"{self.baseurl}/api/v1/rag/split-doc"

        payload = {
            "text": text,
            "chunk_size": chunk_size,
            "separators": separators or ["\n\n", "\n", " ", ""]
        }

        return self.request("POST", url, json=payload)


    def get_collections(self):

        url = f"{self.baseurl}/api/v1/rag/collections"

        return self.request("GET", url)


    def create_collection(self, collection_name, embed_model):

        url = f"{self.baseurl}/api/v1/rag/create-collection"

        json = {
            "collection_name": collection_name,
            "embed_model": embed_model
        }

        return self.request("POST", url, json=json)


    def delete_by_filter(self, collection_name, filter_dict):

        url = f"{self.baseurl}/api/v1/rag/del-by-filter"

        json = {
            "collection_name": collection_name,
            "filter": filter_dict
        }

        return self.request("DELETE", url, json=json)


    def get_embedding(self, text_block, embed_model, separators=None, chunk_size=None, timeout=10):

        url = f"{self.baseurl}/api/v1/rag/embed_text"

        payload = {
            "text": text_block,
            "embed_model": embed_model
        }

        if separators:
            payload["separators"] = separators

        if chunk_size:
            payload["chunk_size"] = chunk_size

        return self.request("POST", url, json=payload, timeout=timeout)


    def add_points(self, embed_model, collection_name, vectors, texts=None, metadata={}, timeout=10):

        url = f"{self.baseurl}/api/v1/rag/add_points"

        payload = {
            "embed_model": embed_model,
            "collection_name": collection_name,
            "vectors": vectors,
            "texts": texts,
            "metadata": metadata or {}
        }

        return self.request("POST", url, json=payload, timeout=timeout)
