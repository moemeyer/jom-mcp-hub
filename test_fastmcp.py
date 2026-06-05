from fastmcp import FastMCP
mcp = FastMCP("test")
app = mcp.http_app()
print(type(app))
