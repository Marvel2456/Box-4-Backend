import re
import django.utils.cache

# Compatibility patch for Django 5.1+ / DRF yasg cache delimiter
if not hasattr(django.utils.cache, 'cc_delim_re'):
    django.utils.cache.cc_delim_re = re.compile(r'\s*,\s*')
