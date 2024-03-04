# Makefile providing various facilities to manage translations

TEMPLATE = extractable.pot
MIN_COMPLETION = 0.20
POFILES = $(wildcard *.po)
LANGS = $(POFILES:%.po=%)

all: update merge

update:
	@cd ../godot; python3 ../scripts/extract_extractable.py

merge:
	@for po in $(POFILES); do \
	  echo -e "\nMerging $$po..."; \
	  msgmerge -w 80 -C $$po $$po $(TEMPLATE) > "$$po".new; \
	  mv -f "$$po".new $$po; \
	  msgattrib --output-file=$$po --no-obsolete $$po; \
	done

check:
	@for po in $(POFILES); do msgfmt -c $$po -o /dev/null; done

# Export translation files with a high enough completion ratio.
# Completion ratio is derived from statistics string such as:
# 2775 translated messages, 272 fuzzy translations, 151 untranslated messages.
# First number can be 0, second and third numbers are only present if non-zero.
export:
	@dest=../godot/editor/translations/extractable; \
	mkdir -p $$dest; \
	cp -f runtime_translations.gen.h $$dest/runtime_translations.gen.h; \
	for po in $(POFILES); do \
	  res=`msgfmt --statistics $$po -o /dev/null 2>&1 | sed 's/[^0-9,]*//g'`; \
	  complete=`cut -d',' -f1 <<< $$res`; \
	  fuzzy_or_untranslated=`cut -d',' -f2 <<< $$res`; \
	  untranslated_maybe=`cut -d',' -f3 <<< $$res`; \
	  if [ -z "$$fuzzy_or_untranslated" ]; then fuzzy_or_untranslated=0; fi; \
	  if [ -z "$$untranslated_maybe" ]; then untranslated_maybe=0; fi; \
	  incomplete=`expr $$fuzzy_or_untranslated + $$untranslated_maybe`; \
	  if `awk "BEGIN {exit !($$complete / ($$complete + $$incomplete) > $(MIN_COMPLETION))}"`; then \
	    echo $$po; \
	    msgattrib -w 80 --translated --no-fuzzy --no-location $$po | sed -e "/^#\. .*/d" > $$dest/$$po; \
	  fi; \
	done;
