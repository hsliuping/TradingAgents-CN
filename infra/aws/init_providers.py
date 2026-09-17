"""Restore missing provider/catalog seed records without changing existing config.

Run inside the deployed backend container. No users or API credentials are imported.
"""
import json
import os
from pathlib import Path

from bson import json_util
from pymongo import MongoClient


PROVIDER_FIELDS = {
    "name", "display_name", "description", "website", "api_doc_url",
    "logo_url", "supported_features", "default_base_url", "test_model",
    "is_aggregator", "aggregator_type", "model_name_format", "created_at",
    "updated_at",
}


def main():
    candidates = sorted(Path('/app/install').glob('database_export_config*.json'))
    seed = None
    for candidate in reversed(candidates):
        document = json_util.loads(candidate.read_text(encoding='utf-8'))
        data = document.get('data', {})
        if data.get('llm_providers'):
            seed = data
            break
    if seed is None:
        raise RuntimeError('No provider seed export found; no database changes made')
    client = MongoClient(os.environ['MONGODB_URL'])
    try:
        db = client[os.environ['MONGODB_DATABASE']]
        added = 0
        for record in seed['llm_providers']:
            provider = {k: v for k, v in record.items() if k in PROVIDER_FIELDS}
            if not provider.get('name'):
                raise ValueError('Provider seed has no name')
            provider.update(api_key='', api_secret='', is_active=False,
                            extra_config={'source': 'seed'})
            result = db.llm_providers.update_one(
                {'name': provider['name']}, {'$setOnInsert': provider}, upsert=True,
            )
            added += int(result.upserted_id is not None)
        catalog_added = 0
        for record in seed.get('model_catalog', []):
            catalog = {k: v for k, v in record.items() if k in {
                'provider', 'provider_name', 'models', 'created_at', 'updated_at',
            }}
            if not catalog.get('provider'):
                continue
            result = db.model_catalog.update_one(
                {'provider': catalog['provider']}, {'$setOnInsert': catalog}, upsert=True,
            )
            catalog_added += int(result.upserted_id is not None)
        print(json.dumps({'providers_added': added, 'catalogs_added': catalog_added,
                          'providers_total': db.llm_providers.count_documents({})}))
    finally:
        client.close()


if __name__ == '__main__':
    main()
