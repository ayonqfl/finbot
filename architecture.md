### --- Without streaming current architecture ---
User sends message
       |
       v
    run_agent()
       |
       v
  Generate SQL
       |
       v
  Execute SQL
       |
       v
  Generate complete answer
       |
       v
  Return JSON response
       |
       v
  Display complete answer


### ---Plan to change with streaming architecture ---
User sends message
       |
       v
    run_agent()
       |
       |---- SSE: status = thinking
       |
       v
  _extract_symbol()
       |
       v
  _wants_report()
       |
       v
  generate_and_execute()
       |
       |---- SSE: status = generating_sql
       |
       v
  Generate SQL using Gemini
       |
       |---- SSE: status = executing_query
       |
       v
  Execute SQL
       |
       v
  Generate answer using Gemini Streaming API
       |
       |---- SSE: chunk = "Your"
       |---- SSE: chunk = " portfolio"
       |---- SSE: chunk = " value"
       |---- SSE: chunk = " is..."
       |
       v
  SSE: status = completed
       |
       v
  Frontend displays continuously