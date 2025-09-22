"""Provide the Preferences class."""

from __future__ import annotations

from json import dumps
from typing import TYPE_CHECKING

from ..const import API_PATH

if TYPE_CHECKING:  # pragma: no cover
    import praw


class Preferences:
    """A class for Reddit preferences.

    The :class:`.Preferences` class provides access to the Reddit preferences of the
    currently authenticated user.

    """

    def __call__(self) -> dict[str, bool | int | str]:
        """Return the preference settings of the authenticated user as a dict.

        This method is intended to be accessed as ``reddit.user.preferences()`` like so:

        .. code-block:: python

            preferences = reddit.user.preferences()
            print(preferences["show_link_flair"])

        See https://www.reddit.com/dev/api#GET_api_v1_me_prefs for the list of possible
        values.

        """
        return self._reddit.get(API_PATH["preferences"])

    def __init__(self, reddit: praw.Reddit):
        """Initialize a :class:`.Preferences` instance.

        :param reddit: The :class:`.Reddit` instance.

        """
        self._reddit = reddit

    def update(self, **preferences: bool | int | str) -> dict[str, bool | int | str]:
        """Modify the specified settings.

        :param accept_pms: Who can send you personal messages (one of ``"everyone"`` or
            ``"whitelisted"``).
        :param activity_relevant_ads: Allow Reddit to use your activity on Reddit to
            show you more relevant advertisements.
        :param allow_clicktracking: Allow Reddit to log my outbound clicks for
            personalization.
        :param beta: I would like to beta test features for Reddit.
        :param clickgadget: Show me links I've recently viewed.
        :param collapse_read_messages: Collapse messages after I've read them.
        :param compress: Compress the link display.
        :param creddit_autorenew: Use a creddit to automatically renew my gold if it
            expires.
        :param default_comment_sort: Default comment sort (one of ``"confidence"``,
            ``"top"``, ``"new"``, ``"controversial"``, ``"old"``, ``"random"``,
            ``"qa"``, or ``"live"``).
        :param bool domain_details: Show additional details in the domain text when
            available, such as the source subreddit or the content author's url/name.
        :param bool email_chat_request: Send chat requests as emails.
        :param bool email_comment_reply: Send comment replies as emails.
        :param bool email_digests: Send email digests.
        :param bool email_messages: Send messages as emails.
        :param bool email_post_reply: Send post replies as emails.
        :param bool email_private_message: Send private messages as emails.
        :param bool email_unsubscribe_all: Unsubscribe from all emails.
        :param bool email_upvote_comment: Send comment upvote updates as emails.
        :param bool email_upvote_post: Send post upvote updates as emails.
        :param bool email_user_new_follower: Send new follower alerts as emails.
        :param bool email_username_mention: Send username mentions as emails.
        :param bool enable_default_themes: Use Reddit theme.
        :param bool feed_recommendations_enabled: Enable feed recommendations.
        :param str geopopular: Location (one of ``"GLOBAL"``, ``"AR"``, ``"AU"``,
            ``"BG"``, ``"CA"``, ``"CL"``, ``"CO"``, ``"CZ"``, ``"FI"``, ``"GB"``,
            ``"GR"``, ``"HR"``, ``"HU"``, ``"IE"``, ``"IN"``, ``"IS"``, ``"JP"``,
            ``"MX"``, ``"MY"``, ``"NZ"``, ``"PH"``, ``"PL"``, ``"PR"``, ``"PT"``,
            ``"RO"``, ``"RS"``, ``"SE"``, ``"SG"``, ``"TH"``, ``"TR"``, ``"TW"``,
            ``"US"``, ``"US_AK"``, ``"US_AL"``, ``"US_AR"``, ``"US_AZ"``, ``"US_CA"``,
            ``"US_CO"``, ``"US_CT"``, ``"US_DC"``, ``"US_DE"``, ``"US_FL"``,
            ``"US_GA"``, ``"US_HI"``, ``"US_IA"``, ``"US_ID"``, ``"US_IL"``,
            ``"US_IN"``, ``"US_KS"``, ``"US_KY"``, ``"US_LA"``, ``"US_MA"``,
            ``"US_MD"``, ``"US_ME"``, ``"US_MI"``, ``"US_MN"``, ``"US_MO"``,
            ``"US_MS"``, ``"US_MT"``, ``"US_NC"``, ``"US_ND"``, ``"US_NE"``,
            ``"US_NH"``, ``"US_NJ"``, ``"US_NM"``, ``"US_NV"``, ``"US_NY"``,
            ``"US_OH"``, ``"US_OK"``, ``"US_OR"``, ``"US_PA"``, ``"US_RI"``,
            ``"US_SC"``, ``"US_SD"``, ``"US_TN"``, ``"US_TX"``, ``"US_UT"``,
            ``"US_VA"``, ``"US_VT"``, ``"US_WA"``, ``"US_WI"``, ``"US_WV"``, or
            ``"US_WY"``).
        :param bool hide_ads: Hide ads.
        :param bool hide_downs: Don't show me submissions after I've downvoted them,
            except my own.
        :param bool hide_from_robots: Don't allow search engines to index my user
            profile.
        :param bool hide_ups: Don't show me submissions after I've upvoted them, except
            my own.
        :param bool highlight_controversial: Show a dagger on comments voted
            controversial.
        :param bool highlight_new_comments: Highlight new comments.
        :param bool ignore_suggested_sort: Ignore suggested sorts.
        :param bool in_redesign_beta: In redesign beta.
        :param bool label_nsfw: Label posts that are not safe for work.
        :param str lang: Interface language (IETF language tag, underscore separated).
        :param bool legacy_search: Show legacy search page.
        :param bool live_orangereds: Send message notifications in my browser.
        :param bool mark_messages_read: Mark messages as read when I open my inbox.
        :param str media: Thumbnail preference (one of ``"on"``, ``"off"``, or
            ``"subreddit"``).
        :param str media_preview: Media preview preference (one of ``"on"``, ``"off"``,
            or ``"subreddit"``).
        :param int min_comment_score: Don't show me comments with a score less than this
            number (between ``-100`` and ``100``).
        :param int min_link_score: Don't show me submissions with a score less than this
            number (between ``-100`` and ``100``).
        :param bool monitor_mentions: Notify me when people say my username.
        :param bool newwindow: Open links in a new window.
        :param bool nightmode: Enable night mode.
        :param bool no_profanity: Don't show thumbnails or media previews for anything
            labeled NSFW.
        :param int num_comments: Display this many comments by default (between ``1``
            and ``500``).
        :param int numsites: Number of links to display at once (between ``1`` and
            ``100``).
        :param bool organic: Show the spotlight box on the home feed.
        :param str other_theme: Subreddit theme to use (subreddit name).
        :param bool over_18: I am over eighteen years old and willing to view adult
            content.
        :param bool private_feeds: Enable private RSS feeds.
        :param bool profile_opt_out: View user profiles on desktop using legacy mode.
        :param bool public_votes: Make my votes public.
        :param bool research: Allow my data to be used for research purposes.
        :param bool search_include_over_18: Include not safe for work (NSFW) search
            results in searches.
        :param bool send_crosspost_messages: Send crosspost messages.
        :param bool send_welcome_messages: Send welcome messages.
        :param bool show_flair: Show user flair.
        :param bool show_gold_expiration: Show how much gold you have remaining on your
            userpage.
        :param bool show_link_flair: Show link flair.
        :param bool show_location_based_recommendations: Show location based
            recommendations.
        :param bool show_presence: Show presence.
        :param bool show_promote: Show promote.
        :param bool show_stylesheets: Allow subreddits to show me custom themes.
        :param bool show_trending: Show trending subreddits on the home feed.
        :param bool show_twitter: Show a link to your Twitter account on your profile.
        :param bool store_visits: Store visits.
        :param bool theme_selector: Theme selector (subreddit name).
        :param bool third_party_data_personalized_ads: Allow Reddit to use data provided
            by third-parties to show you more relevant advertisements on Reddit.
        :param bool third_party_personalized_ads: Allow personalization of
            advertisements.
        :param bool third_party_site_data_personalized_ads: Allow personalization of
            advertisements using third-party website data.
        :param bool third_party_site_data_personalized_content: Allow personalization of
            content using third-party website data.
        :param bool threaded_messages: Show message conversations in the inbox.
        :param bool threaded_modmail: Enable threaded modmail display.
        :param bool top_karma_subreddits: Top karma subreddits.
        :param bool use_global_defaults: Use global defaults.
        :param bool video_autoplay: Autoplay Reddit videos on the desktop comments page.

        Additional keyword arguments can be provided to handle new settings as Reddit
        introduces them.

        See https://www.reddit.com/dev/api#PATCH_api_v1_me_prefs for the most up-to-date
        list of possible parameters.

        This is intended to be used like so:

        .. code-block:: python

            reddit.user.preferences.update(show_link_flair=True)

        This method returns the new state of the preferences as a ``dict``, which can be
        used to check whether a change went through.

        .. code-block:: python

            original_preferences = reddit.user.preferences()
            new_preferences = reddit.user.preferences.update(invalid_param=123)
            print(original_preferences == new_preferences)  # True, no change

        .. warning::

            Passing an unknown parameter name or an illegal value (such as an int when a
            boolean is expected) does not result in an error from the Reddit API. As a
            consequence, any invalid input will fail silently. To verify that changes
            have been made, use the return value of this method, which is a dict of the
            preferences after the update action has been performed.

        Some preferences have names that are not valid keyword arguments in Python. To
        update these, construct a ``dict`` and use ``**`` to unpack it as keyword
        arguments:

        .. code-block:: python

            reddit.user.preferences.update(**{"third_party_data_personalized_ads": False})

        """
        return self._reddit.patch(
            API_PATH["preferences"], data={"json": dumps(preferences)}
        )
