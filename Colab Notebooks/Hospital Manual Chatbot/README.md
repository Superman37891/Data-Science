This project focused on creating a chatbot using RAG with the Merck hospital manuals to answer questions related to medical practice

I loaded the Llama-2-13B-chat-GGUF model from HuggingFace. I then used RAG with the Merck Hospital Manual to create vector DBs using FAISS with multiple text splitters (using different chunk sizes and overlaps). All of these used the same SentenceTransformerEmbeddings from BAAI/bge-base-en-v1.5

Using these different vector databases and multiple combinations for the parameters max_tokens, temperature, top_p, and top_k, I generated responses for 5 queries that the LLM was supposed to answer using data from the Merck Manuals. 

I then chose one vector DB and set of parameters I liked the most and used a different instance of the Llama-2-13B-chat-GGUF model to evaluate the groundedness of the responsse with respect to the context (the manuals) and the relevance of the responses to the queries.