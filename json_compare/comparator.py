import datetime
import json
import re
from typing import Any

from .log_processor import LogProcessor


class JSONComparator:
    """
    Provides comparison of two JSON-files.
    """

    def __init__(
        self,
        left_file_path: str,
        right_file_path: str,
        target_property: str | None = None,
        properties_to_ignore: list[str] | None = None,
    ):
        """
        :param left_file_path: path to file in .JSON format;
        :param right_file_path: path to file in .JSON format;
        :param target_property: key for JSON-object's property's name to be a key in comparison
        of similar objects nested in an array. For example, you have:
        {"cats": [{"id": 4, "name": "Nyan"}, {"id": 2, "name": "Marx"}]}. If you want to set
        cat's "id" as a target_key, use "DATA.cats.<array>.id". DATA points out to the root
        of your JSON and <array> indicates object with target_key is nested in an array;
        :param properties_to_ignore: a list of objects' properties whose mismatch should be
        ignored in the process of comparing. Checkout target_key's paragraph to see examples
        of correct setting the param's items;
        """
        self.diff_log: LogProcessor = LogProcessor()
        self.target_property: str = target_property if target_property else ""
        self.properties_to_ignore: list[str] = (
            properties_to_ignore if properties_to_ignore else list()
        )
        with open(left_file_path, "r") as file:
            self.left_data = json.load(file)
        with open(right_file_path, "r") as file:
            self.right_data = json.load(file)

    def compare_with_right(self) -> None:
        """
        Looks for how the right JSON-file differs from the left one.
        :return: None;
        """
        self.diff_log.log.clear()
        self.__edit_target_prop_path_root("DATA", "RIGHT")
        self.__compare()
        self.__edit_target_prop_path_root("RIGHT", "DATA")

    def compare_with_left(self) -> None:
        """
        Looks for how the left JSON-file differs from the right one.
        :return: None;
        """
        self.diff_log.log.clear()
        self.__edit_target_prop_path_root("DATA", "LEFT")
        self.__compare(with_actual=False)
        self.__edit_target_prop_path_root("LEFT", "DATA")

    def full_compare(self) -> None:
        """
        Looks for differences between files from both perspectives.
        :return: None;
        """
        self.diff_log.log.clear()
        self.__edit_target_prop_path_root("DATA", "RIGHT")
        self.__compare()
        self.__edit_target_prop_path_root("RIGHT", "LEFT")
        self.__compare(with_actual=False)
        self.__edit_target_prop_path_root("LEFT", "DATA")

    def save_diff_logs(self, path: str = "") -> None:
        """
        Saves recorded logs as a text file.
        :param path: a path to directory where the log with differences will be saved.
        By default, current work directory will be used;
        :return: None;
        """
        log_file_name = f"json_compare_diff_{datetime.date.today()}"
        with open(f"{path}{log_file_name}", "w") as f:
            f.write("\n".join(self.diff_log.log))

    def __edit_target_prop_path_root(self, from_: str, to: str) -> None:
        self.target_property = self.target_property.replace(from_, to)

    def __compare(self, with_actual: bool = True) -> None:
        data1, data2, root_log = self.left_data, self.right_data, "RIGHT"
        if not with_actual:
            data1, data2, root_log = data2, data1, "LEFT"

        match self.left_data:
            case dict():
                self._compare_dicts(root_log, data1, data2)
            case list():
                self._compare_lists(root_log, data1, data2)
            case _:
                raise

    def _compare_dicts(
        self, item_path: str, exp_data: dict[str, Any], act_data: dict[str, Any]
    ) -> None:
        for key, val in exp_data.items():
            self.diff_log.setup_path(item_path, key)
            if key not in act_data:
                self.diff_log.missing_property()
                continue
            if type(val) is dict:
                if isinstance(act_data[key], dict):
                    self._compare_dicts(self.diff_log.curr_path, val, act_data[key])
                else:
                    self.diff_log.incorrect_type(dict(), act_data[key])
                continue
            if type(val) is list:
                if isinstance(act_data[key], list):
                    self._compare_lists(self.diff_log.curr_path, val, act_data[key])
                else:
                    self.diff_log.incorrect_type(list(), act_data[key])

                continue
            if val != act_data[key] and not self.__key_to_ignore():
                self.diff_log.unequal_values(val, act_data[key])

    def _compare_lists(
        self, item_path: str, exp_data: list[Any], act_data: list[Any]
    ) -> None:
        if hasattr(self, "target_key_path"):
            self.__compare_with_nested_obj_prop_respect(item_path, exp_data, act_data)
        else:
            self.__compare_with_items_order_respect(item_path, exp_data, act_data)

    def __compare_with_items_order_respect(
        self, item_path: str, exp_data: list[Any], act_data: list[Any]
    ) -> None:
        exp_data_len, act_data_len = len(exp_data), len(act_data)
        self.__check_array_lengths(item_path, exp_data_len, act_data_len)

        for idx, val in enumerate(exp_data):
            self.diff_log.setup_path(item_path, f"<array>[{idx}]")
            if idx == act_data_len:
                self.diff_log.missing_array_item(val)
                continue
            if type(val) is dict:
                if isinstance(act_data[idx], dict):
                    self._compare_dicts(self.diff_log.curr_path, val, act_data[idx])
                else:
                    self.diff_log.incorrect_type(dict(), act_data[idx])
                continue
            if type(val) is list:
                if isinstance(act_data[idx], list):
                    self._compare_lists(self.diff_log.curr_path, val, act_data[idx])
                else:
                    self.diff_log.incorrect_type(list(), act_data[idx])

                continue
            if val != act_data[idx]:
                self.diff_log.unequal_values(val, act_data[idx])

    def __compare_with_nested_obj_prop_respect(
        self, item_path: str, exp_data: list[Any], act_data: list[Any]
    ) -> None:
        exp_data_len, act_data_len = len(exp_data), len(act_data)
        self.__check_array_lengths(item_path, exp_data_len, act_data_len)

        for idx, val in enumerate(exp_data):
            self.diff_log.setup_path(item_path, f"<array[{idx}]>")
            if type(val) is dict:
                target_prop, target_prop_val = self.__get_target_prop_value(val)
                act_data_similar_idx = self.__get_idx_of_similar_row(
                    target_prop, target_prop_val, act_data
                )
                if act_data_similar_idx is None:
                    self.diff_log.missing_array_item(
                        exp_value=target_prop_val, target_prop=target_prop
                    )
                    continue
                self._compare_dicts(
                    self.diff_log.curr_path, val, act_data[act_data_similar_idx]
                )
                continue
            if type(val) is list:
                if isinstance(act_data[idx], list):
                    self._compare_lists(self.diff_log.curr_path, val, act_data[idx])
                else:
                    self.diff_log.incorrect_type(list(), act_data[idx])

                continue
            if val != act_data[idx]:
                self.diff_log.unequal_values(val, act_data[idx])

    def __check_array_lengths(self, item_path: str, exp_len: int, act_len: int) -> None:
        self.diff_log.setup_path(item_path, f"<array>")
        if exp_len > act_len:
            self.diff_log.lack_of_array_items(exp_len, act_len)
        elif exp_len < act_len:
            self.diff_log.exceeding_array_items(exp_len, act_len)

    def __get_target_prop_value(
        self, object_: dict[str, Any]
    ) -> tuple[str, int | float | str | bool | dict[str, Any] | list[Any] | None]:
        target_key = self.target_property.removeprefix(
            re.sub("\[[^()]*\]", "", self.diff_log.curr_path)
        ).replace(".", "")
        exp_key_val = object_[target_key]
        return target_key, exp_key_val

    def __key_to_ignore(self) -> bool:
        curr_path_without_idx = (
            re.sub("\[[^()]*\]", "", self.diff_log.curr_path)
            .replace("RIGHT", "DATA")
            .replace("LEFT", "DATA")
        )
        return True if curr_path_without_idx in self.properties_to_ignore else False

    @staticmethod
    def __get_idx_of_similar_row(
        prop: str,
        prop_val: int | float | str | bool | dict[str, Any] | list[Any] | None,
        data: list[dict[str, Any]],
    ) -> int | None:
        for idx, obj in enumerate(data):
            act_val = obj.get(prop)
            if act_val == prop_val:
                return idx
        return None
