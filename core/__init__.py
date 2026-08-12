import re
import django.utils.cache
import django.template.context

# 1. Compatibility patch for Django 5.1+ / DRF yasg cache delimiter
if not hasattr(django.utils.cache, 'cc_delim_re'):
    django.utils.cache.cc_delim_re = re.compile(r'\s*,\s*')

# 2. Fix Django #35417 / Unfold admin context.flatten() bug when nested Context objects exist in context.dicts
_original_flatten = django.template.context.BaseContext.flatten

def _safe_flatten(self):
    flat = {}
    for d in self.dicts:
        if isinstance(d, django.template.context.BaseContext):
            flat.update(d.flatten())
        elif isinstance(d, dict):
            flat.update(d)
        elif hasattr(d, "items"):
            flat.update(dict(d.items()))
    return flat

django.template.context.BaseContext.flatten = _safe_flatten
