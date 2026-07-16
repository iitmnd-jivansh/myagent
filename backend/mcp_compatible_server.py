import argparse

from mcp_runtime import run_mcp_server


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the official MCP-compatible MyAgent tool server."
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport to use. Use stdio for desktop MCP clients.",
    )
    args = parser.parse_args()
    run_mcp_server(args.transport)


if __name__ == "__main__":
    main()
