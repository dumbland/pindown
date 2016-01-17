Title: {{ description }}
Category: linklist
Link: {{ url }}
Date: {{ date }}
Tags: {{ tags|join(', ') }}
{% if is_draft == true %}Status: draft
{% endif %}

{% for line in extended.split('\n') %}
> {{ line }}
{% endfor %}
