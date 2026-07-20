import os
import gradio as gr

import time # For measuring latency
import traceback # For debugging
from sentence_transformers import SentenceTransformer
import psycopg2
from pgvector.psycopg2 import register_vector
from pgvector import Vector

HF_TOKEN = os.environ["HF_READ_TOKEN"]

embedding_model = SentenceTransformer("BAAI/bge-small-en-v1.5")

model_name = "mistralai/Mistral-7B-Instruct-v0.2"

from huggingface_hub import InferenceClient
llm_client = InferenceClient(
    provider="hf-inference",
    api_key=HF_TOKEN
)

embedding_cache = {}

def get_embedding(text):
    try:
        # This function is now primarily for single text embeddings, e.g., for user queries.
        if text in embedding_cache:
            return embedding_cache[text]
        embedding = embedding_model.encode(text)
        embedding_cache[text] = embedding
        return embedding.tolist()
    except Exception as e:
        print(f"Error getting embedding for text: {text[:50]}...")
        print(f"Error: {e}")
        return []

GLOBAL_TOP_K=5
GLOBAL_SIMILARITY_THRESHOLD=0.70


# --- Database Connection Details ---
PG_HOST = os.environ["PGSQL_AI_CHATBOT_NEONDB_HOST"]
PG_PORT = 5432
PG_USER = 'neondb_owner'
PG_PASSWORD = os.environ["PGSQL_AI_CHATBOT_NEONDB_PASSWORD"]
PG_DBNAME = 'neondb'

def get_db_connection():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DBNAME,
        sslmode='require' # Add this line to enforce SSL
    )
    register_vector(conn) # Register the pgvector type with psycopg2
    return conn

def format_chunk(row):
    return {
        "chunk_id": row[0],
        "text": row[1],
        "page_numbers": row[2],
        "source_header": row[3],
        "source_subheader": row[4],
        "block_type": row[5],
        "similarity": row[6]
    }

def format_keyword_chunk(row):
  return {
      'chunk_id': row[0],
      'text': row[1],
      'page_numbers': row[2],
      'source_header': row[3],
      'source_subheader': row[4],
      'block_type': row[5],
      'rank': row[6] # Include the rank
  }

def vector_search(query_embedding, top_k=GLOBAL_TOP_K, similarity_threshold=GLOBAL_SIMILARITY_THRESHOLD, filter_block_types=None):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Build the WHERE clause for filtering by block_type
        where_clause = ""
        if filter_block_types:
            # Ensure filter_block_types is a tuple or list for the IN clause
            if isinstance(filter_block_types, str):
                filter_block_types = (filter_block_types,)
            placeholders = ', '.join(['%s'] * len(filter_block_types))
            where_clause = f"WHERE block_type IN ({placeholders})"

        # Perform a vector similarity search using cosine similarity (1 - cosine distance).
        # The <=> operator computes cosine distance. 1 - (cosine distance) gives cosine similarity.
        # ORDER BY DESC for closest matches (highest similarity).
        # The LIMIT k clause restricts the number of results.
        query_sql = f"""
            SELECT
                chunk_id,
                text,
                page_numbers,
                source_header,
                source_subheader,
                block_type,
                1 - (embedding <=> %s) AS similarity
            FROM
                document_chunks
            {where_clause}
            ORDER BY
                similarity DESC
            LIMIT %s;
        """

        # Prepare parameters for the query
        # Explicitly cast the query_embedding to a Vector object

        params = [Vector(query_embedding)]

        if filter_block_types:
            params.extend(filter_block_types)
        params.append(top_k)

        cur.execute(query_sql, params)
        results = cur.fetchall()

        # Convert results to a more readable format (list of dictionaries)
        search_results = []
        for row in results:
          if row[6] >= similarity_threshold:
            search_results.append(format_chunk(row))
        return search_results

    except Exception as e:
        print("Error during vector_search")
        traceback.print_exc()
        return []
    finally:
        if conn:
            conn.close()

def keyword_search(keyword_query, top_k=GLOBAL_TOP_K):
  conn = None
  try:
    conn = get_db_connection()
    cur = conn.cursor()
    # Perform keyword search
    cur.execute("""
      SELECT
          chunk_id,
          text,
          page_numbers,
          source_header,
          source_subheader,
          block_type,
          ts_rank(search_vector, plainto_tsquery('english', %s)) AS rank
      FROM document_chunks
      WHERE search_vector @@ plainto_tsquery('english', %s)
      ORDER BY rank DESC
      LIMIT %s;
      """, (keyword_query, keyword_query, top_k))
    results = cur.fetchall()

    keyword_search_results = []
    for row in results:
        keyword_search_results.append(format_keyword_chunk(row))
    return keyword_search_results

  except Exception as e:
    print("Error during keyword_search")
    traceback.print_exc()
    return []
  finally:
    if conn:
      conn.close()

def get_relevant_pages(relevant_chunks):
  # Collect all page numbers, maintaining relevance order and ensuring uniqueness.
  ordered_unique_pages = []
  seen_pages = set()

  for chunk in relevant_chunks:
    if chunk.get('page_numbers'):
      for page_num in chunk['page_numbers']:
        if page_num not in seen_pages:
          ordered_unique_pages.append(page_num)
          seen_pages.add(page_num)

  return ordered_unique_pages

def setup_prompt(query_text, relevant_chunks):
  try:
    parts = [f"""
    You are an expert on PostgreSQL documentation.

    Use the Retrieved Documentation as your primary source of truth.
    If the documentation fully answers the question, answer only from it.
    If the documentation is incomplete, explicitly state what information was missing before using general PostgreSQL knowledge.

    Always clearly state the source of your answer at the end, choosing *one* of the following two options:
    1. 'Answer Source: PostgreSQL Documentation.' (If the answer is derived primarily or entirely from the provided documentation.)
    2. 'Answer Source: General PostgreSQL Knowledge.' (If the answer relies significantly on knowledge outside the provided documentation.)

    Never invent documentation that was not retrieved.
    When answering, synthesize information from *all* relevant retrieved chunks to provide a comprehensive answer, especially if the query has multiple parts.

    """]
    if relevant_chunks:
      parts.append("\nRetrieved Documentation:\n\n")
      for i, chunk in enumerate(relevant_chunks, 1):
          parts.append(
              f"[Chunk {i}]\n"
              f"Header: {chunk['source_header']}\n"
              f"Subheader: {chunk['source_subheader']}\n"
              f"Page Numbers: {chunk['page_numbers']}\n"
              f"Text:\n{chunk['text']}\n\n"
          )
    parts.append(f"\nQuestion: {query_text}\n")
    prompt = "\n".join(parts)
    return prompt
  except Exception as e:
    print("Error in setup_prompt")
    traceback.print_exc()
    return []

def sort_combined_chunks(chunk_item):
  similarity = chunk_item.get('similarity')
  rank = chunk_item.get('rank')

  if similarity is not None:
      # Group 0: Chunks with a valid similarity score (from vector search).
      # Sort primarily by similarity (descending: higher is better).
      # Use rank as a secondary sort key (descending) if available, otherwise 0.0.
      return (0, -similarity, -(rank if rank is not None else 0.0))
  elif rank is not None:
      # Group 1: Chunks with a valid rank score (from keyword search), but no similarity.
      # Use a large positive float for the similarity slot to push these after similarity-based chunks.
      # Sort by rank (descending: higher is better).
      return (1, float('inf'), -rank)
  else:
      # Group 2: Chunks with neither similarity nor rank.
      # Use large positive floats for both similarity and rank slots to push these to the end.
      return (2, float('inf'), float('inf'))

def get_answer(query_text, llm_model, top_k=GLOBAL_TOP_K, use_hybrid_search=True, debug=False):
  # Call the LLM to answer the question from setup_prompt
  start_time = time.time()
  try:
    #print("Generating embedding...")
    query_embedding = get_embedding(query_text)
    query_embedding_end_time = time.time()
    query_embedding_latency = query_embedding_end_time - start_time

    relevant_chunks = []
    if use_hybrid_search:
        # Perform vector search
        vector_results = []
        if query_embedding is not None:
            vector_results = vector_search(query_embedding, top_k=top_k)
        if not vector_results:
            vector_results = []

        # Perform keyword search
        keyword_results = keyword_search(query_text, top_k=top_k)
        if not keyword_results:
            keyword_results = []

        # Combine and de-duplicate results
        combined_chunks_map = {chunk['chunk_id']: chunk for chunk in vector_results}
        for chunk in keyword_results:
            # If a chunk_id already exists from vector search, we keep the vector search result
            # to prioritize more complete metadata (similarity is present).
            if chunk['chunk_id'] not in combined_chunks_map:
                combined_chunks_map[chunk['chunk_id']] = chunk

        # Convert back to list and sort.
        # Prioritize chunks with a 'similarity' (from vector search), then by 'rank' (from keyword search).
        relevant_chunks = sorted(list(combined_chunks_map.values()), key=sort_combined_chunks)[:top_k]

    elif query_embedding is not None:
        # Fallback to pure vector search if hybrid search is off or keyword query is empty
        relevant_chunks = vector_search(query_embedding, top_k=top_k)
    elif query_text is not None: # Fallback to pure keyword search if no embedding or no hybrid search
        relevant_chunks = keyword_search(query_text, top_k=top_k)

    retrieval_end_time = time.time()
    retrieval_latency = retrieval_end_time - query_embedding_end_time

    if not relevant_chunks:
      print("No relevant chunks found.")

    # Get the complete prompt that will be sent to the LLM
    full_prompt_sent_to_llm = setup_prompt(query_text, relevant_chunks)
    if debug:
      print("\n--- Retrieved Chunks (for debugging) ---")
      for i, chunk in enumerate(relevant_chunks):
          print(f"Chunk {i+1}:")
          print(f"  Chunk ID: {chunk.get('chunk_id')}")
          print(f"  Block Type: {chunk.get('block_type')}")
          print(f"  Header: {chunk.get('source_header')}")
          print(f"  Subheader: {chunk.get('source_subheader')}")
          print(f"  Pages: {chunk.get('page_numbers')}")
          print(f"  Text (first 150 chars): {chunk.get('text', '')[:150]}...")
          if 'similarity' in chunk: print(f"  Cosine Similarity: {chunk['similarity']}")
          if 'rank' in chunk: print(f"  Rank: {chunk['rank']}")
          print("--------------------------------------------------")
      print("\n--- Full Prompt Sent to LLM (for debugging) ---")
      print(full_prompt_sent_to_llm)
      print("\n--- END DEBUGGING ---")
      # --- END DEBUGGING
    # Pass prompt to an LLM
    try:
        completion = llm_client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": full_prompt_sent_to_llm
                }
            ],
            max_tokens=500,
            temperature=0.2
        )
    except Exception as e:
        traceback.print_exc()
        return "The language model could not generate a response."

    llm_answer = completion.choices[0].message.content.strip()

    relevant_page_numbers = get_relevant_pages(relevant_chunks)
    if not relevant_page_numbers:
      llm_answer += "\nNo relevant pages found."
    else:
      llm_answer += f'\nRelevant page numbers of PostgreSQL 18 Official Documentation: {relevant_page_numbers}\n'
    llm_answer_end_time = time.time()
    llm_answer_latency = llm_answer_end_time - retrieval_end_time
    print(f"Query embedding latency: {query_embedding_latency:.3f} seconds")
    print(f"Retrieval latency: {retrieval_latency:.3f} seconds")
    print(f"LLM latency: {llm_answer_latency:.3f} seconds")
    print(f"Total latency: {llm_answer_end_time - start_time:.3f} seconds\n")
    return llm_answer
  except Exception as e:
    print("Error in get_answer")
    traceback.print_exc()
    return []


def answer_question_gradio(question):
    """
    Wrapper function for Gradio interface to call the RAG model.
    """
    print(f"Received question: {question}")
    try:
        response = get_answer(question, llm_client, debug=False) # Set debug=False for deployment
        if response: # Ensure response is not None
            return response
        else:
            return "I could not generate an answer for that question."
    except Exception as e:
        print(f"Error in answer_question_gradio: {e}")
        return "An error occurred while processing your request."

# Create the Gradio interface
iface = gr.Interface(
    fn=answer_question_gradio,
    inputs=gr.Textbox(lines=2, placeholder="Enter your question about PostgreSQL..."),
    outputs="text",
    title="PostgreSQL AI Documentation Assistant",
    description="Ask any question about PostgreSQL documentation and get an answer backed by RAG."
)

iface.launch(share=True)