"""Provide the GildableMixin class."""

from warnings import warn

from ....const import API_PATH
from ....util import _deprecate_args


class GildableMixin:
    """Interface for classes that can be gilded."""

    @_deprecate_args("gild_type", "is_anonymous", "message")
    def award(
        self,
        *,
        gild_type: str = "gid_2",
        is_anonymous: bool = True,
        message: str = None,
    ) -> dict:
        """Award the author of the item.

        :param gild_type: Type of award to give. See table below for currently know
            global award types.
        :param is_anonymous: If ``True``, the authenticated user's username will not be
            revealed to the recipient.
        :param message: Message to include with the award.

        :returns: A dict containing info similar to what is shown below:

            .. code-block:: python

                {
                    "subreddit_balance": 85260,
                    "treatment_tags": [],
                    "coins": 8760,
                    "gildings": {"gid_1": 0, "gid_2": 1, "gid_3": 0},
                    "awarder_karma_received": 4,
                    "all_awardings": [
                        {
                            "giver_coin_reward": 0,
                            "subreddit_id": None,
                            "is_new": False,
                            "days_of_drip_extension": 0,
                            "coin_price": 75,
                            "id": "award_9663243a-e77f-44cf-abc6-850ead2cd18d",
                            "penny_donate": 0,
                            "coin_reward": 0,
                            "icon_url": "https://www.redditstatic.com/gold/awards/icon/SnooClappingPremium_512.png",
                            "days_of_premium": 0,
                            "icon_height": 512,
                            "tiers_by_required_awardings": None,
                            "icon_width": 512,
                            "static_icon_width": 512,
                            "start_date": None,
                            "is_enabled": True,
                            "awardings_required_to_grant_benefits": None,
                            "description": "For an especially amazing showing.",
                            "end_date": None,
                            "subreddit_coin_reward": 0,
                            "count": 1,
                            "static_icon_height": 512,
                            "name": "Bravo Grande!",
                            "icon_format": "APNG",
                            "award_sub_type": "PREMIUM",
                            "penny_price": 0,
                            "award_type": "global",
                            "static_icon_url": "https://i.redd.it/award_images/t5_q0gj4/59e02tmkl4451_BravoGrande-Static.png",
                        }
                    ],
                }


        .. warning::

            Requires the authenticated user to own Reddit Coins. Calling this method
            will consume Reddit Coins.

        To award the gold award anonymously do:

        .. code-block:: python

            comment = reddit.comment("dkk4qjd")
            comment.award()

            submission = reddit.submission("8dmv8z")
            submission.award()

        To award the platinum award with the message 'Nice!' and reveal your username to
        the recipient do:

        .. code-block:: python

            comment = reddit.comment("dkk4qjd")
            comment.award(gild_type="gild_3", message="Nice!", is_anonymous=False)

            submission = reddit.submission("8dmv8z")
            submission.award(gild_type="gild_3", message="Nice!", is_anonymous=False)

        .. include:: awards.txt

        """
        params = {
            "api_type": "json",
            "gild_type": gild_type,
            "is_anonymous": is_anonymous,
            "thing_id": self.fullname,
            "message": message,
        }
        return self._reddit.post(API_PATH["award_thing"], params=params)

    def gild(self) -> dict:
        """Alias for :meth:`.award` to maintain backwards compatibility."""
        warn(
            "'.gild' has been renamed to '.award'.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.award()
