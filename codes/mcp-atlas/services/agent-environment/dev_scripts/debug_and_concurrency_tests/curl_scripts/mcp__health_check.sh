#!/bin/bash
curl -w " HTTP_STATUS:%{http_code}\n" -m 5 http://localhost:1984/health
