Title: {{ description }}
Category: linklist
Link: {{ url }}
Date: {{ date }}
Tags: {{ tags|join(', ') }}
Status: draft

{% for line in extended.split('\n') %}
> {{ line }}
{% endfor %}