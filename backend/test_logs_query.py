#!/usr/bin/env python3
"""Test the LogsQueryClient to see what error we get from Usage table query"""
import asyncio
import logging
from datetime import timedelta
from azure.monitor.query import LogsQueryClient
from azure.identity import DefaultAzureCredential

logging.basicConfig(level=logging.DEBUG)

async def test_logs_query():
    credential = DefaultAzureCredential()
    client = LogsQueryClient(credential=credential)

    workspace_id = "/subscriptions/a1ba82d0-9b2b-4d22-827a-88e607cf6ca8/resourceGroups/PCS-Sentinel-RG/providers/microsoft.operationalinsights/workspaces/PCS-Sentinel-Demo"

    query = "Usage | take 5"

    print(f"Testing LogsQueryClient.query_workspace()")
    print(f"Workspace ID: {workspace_id}")
    print(f"Query: {query}")
    print("")

    try:
        response = client.query_workspace(
            workspace_id=workspace_id,
            query=query,
            timespan=timedelta(days=30)
        )
        print(f"SUCCESS! Got {len(response.tables)} tables")
        if response.tables:
            print(f"First table rows: {response.tables[0].rows[:3]}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_logs_query())
